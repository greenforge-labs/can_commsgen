# PLC Code Generation

## Problem
Given a normalised schema model, produce all PLC Structured Text files.

## Goal
`can_commsgen/plc.py` provides a `generate_plc(schema: Schema, output_dir: Path)` function that writes all PLC files to the output directory. Jinja2 templates in `templates/plc/` define the output format.

## Scope

### Generated files (one Jinja2 template each)
- `{EnumName}.st` — one per enum (template: `enum.st.j2`)
- `CAN_EXTRACT_BITS.st` — bit unpack helper (template: `bit_helpers.st.j2` or split into two)
- `CAN_INSERT_BITS.st` — bit pack helper
- `{MSG_NAME_UPPER}_RECV.st` — one per pc_to_plc message (template: `recv_fb.st.j2`)
- `{MSG_NAME_UPPER}_SEND.st` — one per plc_to_pc message (template: `send_fb.st.j2`)
- `GVL.st` — global variable list for received fields + timeout booleans (template: `gvl.st.j2`)
- `main_input.st` — calls all RECV FBs (template: `main_input.st.j2`)

### Key generation rules
- All files start with `(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)`
- RECV FBs: check DLC, extract fields into GVL, manage timeout via TON timer
- SEND FBs: fields as VAR_INPUT, pack into data array, transmit via CAN_Tx
- SEND FBs use REAL_TO_INT for signed reals, REAL_TO_UINT for unsigned reals
- GVL only contains pc_to_plc fields (received) plus `{messageName}WithinTimeout` booleans
- main_input.st passes `ifmDevice.CAN_CHANNEL.{can_channel}` to each RECV FB
- Enum backing type: smallest IEC integer fitting max value (USINT/UINT/UDINT/ULINT)

## What NOT to change
- Golden files (tests compare against them), schema model, design.md

## Testing
- Snapshot tests: generate PLC from `tests/fixtures/example_schema.yaml`, compare each output file against `tests/golden/plc/` byte-for-byte
- Test in `tests/test_plc_gen.py`

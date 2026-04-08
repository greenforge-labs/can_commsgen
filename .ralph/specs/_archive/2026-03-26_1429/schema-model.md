# Schema Model

## Problem
The generator needs to load YAML schemas, validate them, resolve enum references, infer wire types, compute bit offsets, and produce a normalised model that PLC/C++/report generators consume.

## Goal
`can_commsgen/schema.py` provides dataclasses for the schema model and a `load_schema(paths: list[Path]) -> Schema` function that takes one or more YAML files and returns a fully resolved, validated, bitpacked schema model.

## Scope

### Dataclasses
- `Schema` — top-level: plc config, list of enums, list of messages
- `PlcConfig` — can_channel string
- `EnumDef` — name, values dict, derived wire_bits and backing_type
- `MessageDef` — name, id, direction, timeout_ms (optional), list of fields, derived dlc
- `FieldDef` — name, type, min/max/resolution/unit (all optional), plus derived: wire_bits, wire_signed, bit_offset, wire_min, wire_max, plc_var_name, cpp_var_name

### Wire type inference (must match design.md section 2.4 exactly)
- `real`: wire_min/max from min/max/resolution, signed if min<0, bits from formula
- Integer with min/max: bits from range, signedness from type name
- Integer bare: full width of endpoint type
- `bool`: 1 bit
- Enum: bits from ceil(log2(max_value + 1))

### Naming transforms
- PLC: snake_case field name → camelCase, append `_unit` if unit present
- C++: keep snake_case, append `_unit` if unit present
- FB names: `MOTOR_COMMAND_RECV` / `DRIVE_STATUS_SEND`
- Struct names: `MotorCommand`, `DriveStatus` (PascalCase from snake_case)

### Validation (errors, not warnings)
- `type: real` missing min, max, or resolution
- `resolution` on non-real type
- `min`/`max` on bool or enum
- Integer min/max outside endpoint type range
- Total frame bits > 64
- Duplicate CAN IDs (regardless of direction)
- Enum type referencing undeclared enum
- Unsigned type with min < 0

### JSON Schema
Ship a `schema.json` for structural validation of the YAML, used during loading.

## What NOT to change
- Golden files, C++ roundtrip tests, design.md

## Testing
- `test_schema.py` with table-driven tests for each wire inference case (use the worked examples from design.md section 2.4)
- Table-driven validation error tests: one `(yaml_snippet, expected_error_substring)` per validation rule
- Test naming transforms: `("target_velocity", "rpm")` → `"targetVelocity_rpm"` (PLC), `"target_velocity_rpm"` (C++)
- Test DLC computation: the example schema should produce DLCs of 4, 6, 1
- Test loading the full example_schema.yaml fixture and verify the model matches expected values

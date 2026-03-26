# Rich Error Messages

## Problem
When schema validation fails, the current implementation raises single-line `SchemaError` messages (e.g. `"motor_command: total frame bits (68) exceeds maximum of 64"`). These are correct but unhelpful — the user has to mentally reconstruct which fields contributed to the overflow, what their bit widths are, and what they could change to fix it.

Design.md section 5.2 specifies detailed, multi-line error messages with field breakdowns, computed values, and actionable suggestions. None of this is implemented.

## Goal
Replace terse `SchemaError` messages with the rich, multi-line formats specified in design.md section 5.2. Three error categories need rich formatting:

### 1. Frame overflow (Rule 5: total bits > 64)
Current: `"motor_command: total frame bits (68) exceeds maximum of 64"`

Target:
```
ERROR: Message 'drive_status' (0x00000200) exceeds CAN frame capacity.
  Total packed size: 68 bits (8.5 bytes)
  CAN maximum:      64 bits (8 bytes)
  Overflow:          4 bits

  Field breakdown:
    actual_velocity   16 bits  (bit 0..15)
    motor_temp        12 bits  (bit 16..27)
    bus_voltage       10 bits  (bit 28..37)
    fault_code         8 bits  (bit 38..45)
    error_detail      22 bits  (bit 46..67)  ← exceeds frame at bit 64

  Suggestions:
    - Reduce the range (min/max) of one or more fields
    - Increase the resolution of real-valued fields (fewer bits per field)
    - Split this message into two messages
```

### 2. Field-level inference warnings (large bit usage from fine resolution)
Not currently emitted at all. Target:
```
ERROR: Field 'pressure' in message 'sensor_data' (0x00000400):
  type: real, min: -100.0, max: 5000.0, resolution: 0.001
  Inferred wire range: [-100000, 5000000] → requires 23 bits (signed)

  This single field uses 23 of 64 available bits.
  Consider whether resolution: 0.001 is necessary, or widen to 0.01 (→ 20 bits)
  or 0.1 (→ 16 bits).
```
Note: this is specifically a warning within the frame overflow error context, not an independent error. It fires when a single `real` field's bit width is large relative to 64 bits, and the message overflows. It is not a standalone validation rule.

### 3. Range vs endpoint type mismatch (Rule 4)
Current: `"motor_command.target_velocity: range [-100, 1024] exceeds uint8 bounds [0, 255]"`

Target:
```
ERROR: Field 'counter' in message 'heartbeat' (0x00000500):
  type: uint8, min: 0, max: 1024
  max value 1024 exceeds uint8 range [0, 255].

  Either widen the type to uint16, or reduce max to 255.
```

## Scope

### In scope
- Reformatting the three error categories above in `_validate_schema()` within `can_commsgen/schema.py`
- Computing per-field bit widths and cumulative offsets for the frame overflow breakdown (the logic already exists in the function — it just needs to be captured per-field instead of only as a running total)
- Updating existing tests in `tests/test_schema.py` that assert on error message content to match the new format

### NOT in scope
- Adding new validation rules — all rules are already implemented and correct
- Changing which conditions trigger errors
- Changing the `SchemaError` exception class itself
- Modifying any other module (`plc.py`, `cpp.py`, `report.py`, `cli.py`)
- Modifying golden files or generation output

## Details

### Implementation location
All changes are in `can_commsgen/schema.py`, specifically the `_validate_schema()` function (currently lines 315–425). The function already computes per-field bit widths inline for the Rule 5 total — refactor to accumulate a list of `(field_name, bit_width)` tuples as it iterates, then use that list to build the breakdown string when the overflow error fires.

### Field breakdown alignment
Use fixed-width formatting for the field breakdown table. Field names left-justified, bit counts right-justified, offset ranges in parentheses. Mark the first field that crosses bit 64 with `← exceeds frame at bit 64`.

### Suggestion text
The suggestion lines in the frame overflow error are static text — they don't need to be dynamically generated based on field types.

### Existing tests to update
`tests/test_schema.py` has parametrized tests for validation rules that use `pytest.raises(SchemaError, match=...)`. These patterns will need updating to match the new multi-line message format. The tests should still verify the same error conditions trigger, just with updated `match` patterns.

### Error message is the full `SchemaError` string
The rich format is the exception message itself (what `str(error)` returns). The CLI catches `SchemaError` and prints it — no changes needed there.

## What NOT to change
- `cli.py` — already prints `SchemaError` messages correctly
- `plc.py`, `cpp.py`, `report.py` — unrelated to validation
- `design.md` — the spec, not the implementation
- Golden files — no generation output changes
- The set of validation rules — all 8 rules stay as-is

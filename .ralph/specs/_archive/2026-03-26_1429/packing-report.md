# Packing Report Generation

## Problem
Users need a human-readable summary of how messages are packed for code review and debugging.

## Goal
`can_commsgen/report.py` provides a `generate_report(schema: Schema, output_path: Path)` function that writes a text packing report.

## Scope

### Report contents (per message)
- Message name, CAN ID (hex), direction, timeout (if set)
- DLC in bytes, total bits used vs 64 max
- Per-field table: bit offset, bit count, signedness, field name, endpoint type, wire range, physical range with unit, resolution
- Fields without physical range or resolution show `--`

### Format
Fixed-width columns, `=` and `-` separator lines. See `tests/golden/report/packing_report.txt` for the exact format.

## What NOT to change
- Golden files, schema model, design.md

## Testing
- Snapshot test: generate report from `tests/fixtures/example_schema.yaml`, compare against `tests/golden/report/packing_report.txt`
- Test in `tests/test_report_gen.py` (or combine into an integration test file)

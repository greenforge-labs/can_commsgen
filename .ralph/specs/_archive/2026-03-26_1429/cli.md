# CLI

## Problem
Users need a command-line interface to run the generator.

## Goal
A Click-based CLI installed as `can_commsgen` console script that accepts schema files and output paths, then runs the full pipeline.

## Scope

### Interface
```
can_commsgen \
  --schema path/to/schema.yaml \    # repeatable
  --out-plc path/to/plc/dir \
  --out-cpp path/to/cpp/dir \
  --out-report path/to/report.txt   # optional
```

### Behaviour
1. Load and merge all `--schema` files via `schema.load_schema()`
2. Validation errors → print to stderr, exit 1
3. Generate PLC to `--out-plc`
4. Generate C++ to `--out-cpp`
5. If `--out-report` provided, generate packing report
6. Exit 0 on success

### Entry point
Registered as console_scripts in pyproject.toml: `can_commsgen = "can_commsgen.cli:main"` (or similar).

## What NOT to change
- Golden files, schema model, design.md

## Testing
- Smoke test: run CLI against `tests/fixtures/example_schema.yaml` with tmp dirs, verify exit code 0 and that expected files exist
- Error test: run CLI against an invalid schema, verify exit code 1 and error message on stderr
- Test in `tests/test_cli.py`

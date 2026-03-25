# Implementation Plan

**Status**: Nothing is implemented. The repo contains only specifications, golden test files, a C++ roundtrip test harness, and a Nix dev environment.

**Out of scope** (per cpp-generation.md): `can_interface.hpp` / `can_interface.cpp` — deferred to a future loop. The templates `can_interface.hpp.j2` and `can_interface.cpp.j2` listed in design.md section 6.2 should NOT be created in this loop.

---

## Phase 1: Scaffolding

> **Goal**: A working Python package with all dependencies declared, empty modules in place, and quality gates passing on the empty project.

- [x] **1.1 Create `pyproject.toml`** — Project metadata, build system (`hatchling` or `setuptools`), dependencies (`pyyaml`, `jinja2`, `click`, `jsonschema`), dev dependencies (`pytest`, `ruff`, `pyright`), console_scripts entry `can_commsgen = "can_commsgen.cli:main"`.
  - *Why*: Everything else depends on an installable package.
  - *Test*: `pip install -e .` succeeds.

- [x] **1.2 Create `pixi.toml`** — Environment management wrapping Python + dev tools. Should provide `pixi run pytest`, `pixi run ruff`, `pixi run pyright` tasks.
  - *Why*: AGENTS.md specifies pixi as the task runner for all quality gates.
  - *Test*: `pixi install` succeeds, `pixi run ruff --version` works.

- [x] **1.3 Create package structure** — `can_commsgen/__init__.py`, `can_commsgen/schema.py`, `can_commsgen/plc.py`, `can_commsgen/cpp.py`, `can_commsgen/report.py`, `can_commsgen/cli.py`. All modules can be empty stubs (e.g. `cli.py` has a `def main(): pass`).
  - *Why*: Modules must exist for imports and for ruff/pyright to have something to check.
  - *Test*: `python -c "import can_commsgen"` succeeds.

- [x] **1.4 Create template directories** — `templates/plc/` and `templates/cpp/` with empty `.j2` placeholder files (or a `.gitkeep`). Template filenames per design.md 6.2: `enum.st.j2`, `recv_fb.st.j2`, `send_fb.st.j2`, `gvl.st.j2`, `main_input.st.j2`, `bit_helpers.st.j2` (PLC); `can_messages.hpp.j2` (C++).
  - *Why*: Generators need to find templates via a known path relative to the package.
  - *Test*: directories and files exist.

- [x] **1.5 Create `tests/conftest.py`** — Fixture that loads `tests/fixtures/example_schema.yaml` and returns the raw YAML dict. Fixture for golden file paths.
  - *Why*: All test modules will need the example schema.
  - *Test*: `pixi run pytest tests/` passes (with one placeholder test).

- [x] **1.6 Create placeholder test file** — `tests/test_schema.py` with one trivially passing test.
  - *Why*: Validates the test pipeline is wired up.
  - *Test*: All three quality gates pass: `pixi run ruff check can_commsgen/ tests/ && pixi run pyright can_commsgen/ && pixi run pytest tests/`.

---

## Phase 2: Schema Model

> **Goal**: `can_commsgen/schema.py` provides dataclasses and a `load_schema()` function that returns a fully resolved, validated, bitpacked schema model.

- [x] **2.1 Define dataclasses** — `Schema`, `PlcConfig`, `EnumDef`, `MessageDef`, `FieldDef` per schema-model.md. Include all derived fields (`wire_bits`, `wire_signed`, `bit_offset`, `wire_min`, `wire_max`, `plc_var_name`, `cpp_var_name`, `dlc`, `backing_type`).
  - *Why*: These are the data structures consumed by every generator.
  - *Test*: `pixi run pyright can_commsgen/` passes — types are consistent.

- [x] **2.2 Create `schema.json`** — JSON Schema for structural validation of YAML input. Covers required top-level keys (`version`, `plc`, `messages`), enum structure, message structure, field properties, valid type names.
  - *Why*: Provides structural validation before the semantic pipeline runs; also enables VS Code autocomplete per design.md 6.3.
  - *Test*: `tests/fixtures/example_schema.yaml` validates against schema.json. An invalid YAML snippet does not.

- [x] **2.3 Implement YAML loading + JSON Schema validation** — `load_schema(paths: list[Path]) -> Schema` entry point. Load YAML files, merge (combine enums + messages lists), validate against `schema.json` using `jsonschema` library.
  - *Why*: First step of the processing pipeline (design.md 6.4).
  - *Test*: Loading `example_schema.yaml` returns a Schema with 1 enum and 3 messages. Loading invalid YAML raises a clear error.

- [x] **2.4 Implement wire type inference** — Match design.md section 2.4 exactly. Handle all five cases: `real` (wire_min/max from min/max/resolution, bits from formula), integer with range, integer bare, bool (1 bit), enum (ceil(log2(max+1))).
  - *Why*: Core bitpacking logic — all generators depend on correct wire_bits and wire_signed.
  - *Test*: Table-driven tests using the worked examples from design.md: `target_velocity` → 16 bits signed; `torque_limit` → 16 bits unsigned; `motor_temp` → 12 bits signed; `bus_voltage` → 10 bits unsigned; `fault_code` → 8 bits unsigned; `drive_mode` → 2 bits unsigned.

- [x] **2.5 Implement naming transforms** — PLC: `snake_case` → `camelCase` + `_unit`; C++: `snake_case` + `_unit`; FB names: `UPPER_SNAKE_CASE` + `_RECV`/`_SEND`; struct names: `PascalCase`.
  - *Why*: Every generated file uses these transforms.
  - *Test*: `("target_velocity", "rpm")` → PLC `targetVelocity_rpm`, C++ `target_velocity_rpm`. `("fault_code", None)` → PLC `faultCode`, C++ `fault_code`. `"motor_command"` → FB `MOTOR_COMMAND_RECV`, struct `MotorCommand`.

- [x] **2.6 Implement bitpacking + DLC computation** — Assign sequential bit offsets to fields. DLC = ceil(total_bits / 8).
  - *Why*: Bit offsets are needed by every generator; DLC is needed by PLC FBs and C++ parse/build.
  - *Test*: Example schema DLCs: motor_command=4, drive_status=6, pc_state=1. Bit offsets: motor_command fields at 0 and 16; drive_status fields at 0, 16, 28, 38.

- [x] **2.7 Implement validation rules** — All rules from design.md 6.4 and schema-model.md: (1) real missing min/max/resolution, (2) resolution on non-real, (3) min/max on bool/enum, (4) integer range outside endpoint type, (5) frame >64 bits, (6) duplicate CAN IDs, (7) undeclared enum reference, (8) unsigned type with min<0.
  - *Why*: Must reject invalid schemas with clear error messages before generation.
  - *Test*: Table-driven `(yaml_snippet, expected_error_substring)` tests — one per validation rule.

- [x] **2.8 Implement enum backing type derivation** — Smallest IEC/C++ integer type fitting max value: 0-255 → USINT/uint8_t, 256-65535 → UINT/uint16_t, etc.
  - *Why*: Used in PLC enum files and C++ enum class declarations.
  - *Test*: DriveMode (max 3) → USINT/uint8_t. Verify against golden output.

- [x] **2.9 Full example schema integration test** — Load `example_schema.yaml` end-to-end, verify the complete model matches expected values (all wire_bits, bit_offsets, DLCs, names).
  - *Why*: Validates the entire schema pipeline works together.
  - *Test*: Assert all derived values for every field in every message match design.md examples.

---

## Phase 3: PLC Generation

> **Goal**: `can_commsgen/plc.py` generates all PLC ST files matching the golden files byte-for-byte.

- [x] **3.1 Implement `enum.st.j2` template + generation** — Produces `{EnumName}.st` with `qualified_only`, `strict` attributes, values, backing type.
  - *Why*: Enum files are standalone and have no dependencies on other templates.
  - *Test*: Generated `DriveMode.st` matches `tests/golden/plc/DriveMode.st`.

- [x] **3.2 Implement `bit_helpers.st.j2` template + generation** — Produces `CAN_EXTRACT_BITS.st` and `CAN_INSERT_BITS.st`. These are static (no schema data needed), but generated so they ship with the output.
  - *Why*: All RECV/SEND FBs depend on these helpers.
  - *Test*: Generated files match `tests/golden/plc/CAN_EXTRACT_BITS.st` and `tests/golden/plc/CAN_INSERT_BITS.st`.

- [x] **3.3 Implement `recv_fb.st.j2` template + generation** — Produces `{MSG_NAME}_RECV.st` for each `pc_to_plc` message. Includes CAN_Rx, DLC check, field extraction with CAN_EXTRACT_BITS, TON timeout. Uses `REAL_TO_INT` for signed reals, `REAL_TO_UINT` for unsigned reals in scaling expressions. Handles real/integer/bool/enum field types.
  - *Why*: RECV FBs are the PLC's receive path.
  - *Test*: Generated `MOTOR_COMMAND_RECV.st` and `PC_STATE_RECV.st` match golden files.

- [ ] **3.4 Implement `send_fb.st.j2` template + generation** — Produces `{MSG_NAME}_SEND.st` for each `plc_to_pc` message. Field values as VAR_INPUT, CAN_INSERT_BITS packing, CAN_Tx transmission.
  - *Why*: SEND FBs are the PLC's transmit path.
  - *Test*: Generated `DRIVE_STATUS_SEND.st` matches golden file.

- [ ] **3.5 Implement `gvl.st.j2` template + generation** — Produces `GVL.st` with `qualified_only` attribute. Only `pc_to_plc` fields + `{messageName}WithinTimeout` booleans.
  - *Why*: GVL is where RECV FBs store received values.
  - *Test*: Generated `GVL.st` matches golden file.

- [ ] **3.6 Implement `main_input.st.j2` template + generation** — Produces `main_input.st` calling all RECV FBs with `ifmDevice.CAN_CHANNEL.{can_channel}`.
  - *Why*: Wires RECV FBs into the PLC's main scan cycle.
  - *Test*: Generated `main_input.st` matches golden file.

- [ ] **3.7 Wire up `generate_plc()` function** — `plc.py` exposes `generate_plc(schema: Schema, output_dir: Path)` that renders all templates and writes all files.
  - *Why*: Single entry point for PLC generation used by CLI.
  - *Test*: All 8 PLC golden file comparisons pass in `tests/test_plc_gen.py`.

---

## Phase 4: C++ Generation

> **Goal**: `can_commsgen/cpp.py` generates `can_messages.hpp` matching the golden file and passing the C++ roundtrip test.

- [ ] **4.1 Implement `can_messages.hpp.j2` template** — Single template producing the complete header: pragma once, includes (`cmath`, `cstdint`, `optional`, `linux/can.h`), namespace `project_can`, enum classes, message structs, `detail::extract_bits`/`insert_bits` helpers, parse functions (all messages), build functions (all messages).
  - *Why*: The C++ header is the single C++ output file.
  - *Test*: Generated `can_messages.hpp` matches `tests/golden/cpp/can_messages.hpp`.

- [ ] **4.2 Wire up `generate_cpp()` function** — `cpp.py` exposes `generate_cpp(schema: Schema, output_dir: Path)`.
  - *Why*: Single entry point for C++ generation used by CLI.
  - *Test*: Snapshot test in `tests/test_cpp_gen.py` passes.

- [ ] **4.3 C++ roundtrip test integration** — Pytest test that: generates `can_messages.hpp` → copies to `tests/cpp_roundtrip/generated/` → runs cmake build → runs ctest. Skip if no C++ compiler.
  - *Why*: Proves bitpacking correctness end-to-end — the 34 roundtrip tests verify parse(build(x)) == x within resolution.
  - *Test*: `tests/test_cpp_gen.py` C++ roundtrip test passes (all 34 assertions).

---

## Phase 5: Packing Report

> **Goal**: `can_commsgen/report.py` generates a text packing report matching the golden file.

- [ ] **5.1 Implement `generate_report()` function** — Produces fixed-width-column text report with per-message header (name, CAN ID, direction, timeout, DLC, bits used) and per-field table (bit offset, bits, signed, name, type, wire range, physical range with unit, resolution). Fields without physical range show `--`.
  - *Why*: Human-readable report for code review diffs.
  - *Test*: Generated report matches `tests/golden/report/packing_report.txt` in `tests/test_report_gen.py`.

---

## Phase 6: CLI

> **Goal**: A Click-based `can_commsgen` console script that runs the full pipeline.

- [ ] **6.1 Implement Click CLI** — `can_commsgen/cli.py` with `@click.command`, options: `--schema` (required, multiple), `--out-plc` (required), `--out-cpp` (required), `--out-report` (optional). Pipeline: load_schema → generate_plc → generate_cpp → generate_report (if requested). Validation errors print to stderr, exit 1.
  - *Why*: User-facing entry point.
  - *Test*: Smoke test in `tests/test_cli.py` — run against `example_schema.yaml` with tmp dirs, verify exit 0 and expected files exist. Error test — invalid schema gives exit 1 and stderr output.

---

## Phase 7: Integration Tests

> **Goal**: End-to-end confidence that the full pipeline produces correct output.

- [ ] **7.1 End-to-end snapshot test** — Single test that runs the CLI against `example_schema.yaml`, then compares ALL output files (8 PLC + 1 C++ + 1 report) against golden files.
  - *Why*: Catches regressions across the full pipeline in one shot.
  - *Test*: All golden file comparisons pass.

- [ ] **7.2 C++ roundtrip via CLI** — Test that runs CLI to generate, then compiles and runs the C++ roundtrip test.
  - *Why*: Validates the CLI-to-compiled-C++ path works end-to-end.
  - *Test*: cmake build + ctest passes (34 roundtrip assertions).

- [ ] **7.3 Multi-schema merge test** — Split `example_schema.yaml` into two files (e.g. one with motor_command, one with drive_status+pc_state), pass both to CLI, verify output is identical to single-file case.
  - *Why*: design.md specifies multiple schema files are merged before generation.
  - *Test*: Output matches golden files.

---

## Notes

- **Template loading**: Jinja2 templates should be loaded relative to the installed package (use `importlib.resources` or `__file__`-relative paths). Ensure `templates/` is included in the package data in `pyproject.toml`.
- **Golden file comparisons**: Use exact string comparison. If there are trailing newline or whitespace differences, fix the generator — don't alter the golden files.
- **`schema.json` location**: Ship at package root (alongside `can_commsgen/`), include in package data.
- **Enum backing type for PLC**: The `bit_helpers.st.j2` templates are static content (no template variables) — they could be plain `.st` files copied verbatim, or trivial templates. Either approach works.
- **SEND FB scaling**: design.md shows `REAL_TO_INT` for signed reals and `REAL_TO_UINT` for unsigned reals. The template must branch on `wire_signed`.
- **`cmath` include**: The golden C++ file includes `<cmath>` for `std::round` used in build functions.

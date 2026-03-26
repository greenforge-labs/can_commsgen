# Implementation Plan

**Status**: Core generator is complete (schema model, PLC ST, C++ header, packing report, CLI, integration tests — 89 tests passing). Two feature specs remain: CAN interface generation and rich error messages.

**Baseline**: All quality gates pass. `pixi run ruff check && pixi run pyright && pixi run pytest` — 93 tests, 0 errors.

---

## Phase 8: Rich Error Messages

> **Goal**: Replace terse single-line `SchemaError` messages with the detailed, multi-line formats specified in design.md section 5.2. Three error categories get rich formatting.

- [x] **8.1 Refactor frame overflow error (Rule 5)** — In `_validate_schema()` within `schema.py`, accumulate per-field `(field_name, bit_width)` tuples as fields are iterated. When total bits > 64, build a multi-line error with: message name + CAN ID, total packed size vs CAN maximum, overflow count, field breakdown table (left-justified names, right-justified bit counts, offset ranges), `← exceeds frame at bit 64` marker on the first field crossing bit 64, and static suggestion lines.
  - *Why*: The current error `"motor_command: total frame bits (68) exceeds maximum of 64"` gives no visibility into which fields contribute or how to fix it.
  - *Test*: Update existing frame overflow test in `tests/test_schema.py` to match new multi-line format. Verify field breakdown and overflow marker are present.

- [x] **8.2 Add field-level inference warning within frame overflow** — When a message overflows AND contains a `real` field using a large portion of the 64-bit budget (from fine resolution), append a per-field note showing the inferred wire range, bit count, and suggestions to widen resolution.
  - *Why*: Users often don't realize that `resolution: 0.001` on a wide range can consume 23+ bits for a single field.
  - *Test*: Craft a schema with a `real` field using fine resolution that causes overflow. Verify the field-level note appears within the overflow error.

- [x] **8.3 Improve range vs endpoint type mismatch error (Rule 4)** — Reformat the error to show: field name + message context, declared type + min/max, which bound is exceeded and by how much, actionable suggestion (widen type or reduce range).
  - *Why*: Current format `"motor_command.target_velocity: range [-100, 1024] exceeds uint8 bounds [0, 255]"` requires the user to figure out the fix themselves.
  - *Test*: Update existing range mismatch tests in `tests/test_schema.py` to match new multi-line format.

- [x] **8.4 Verify all existing tests pass with updated match patterns** — After reformatting all three error categories, run the full test suite. Existing validation tests that assert on error substrings via `pytest.raises(SchemaError, match=...)` must be updated to match the new format while still verifying the same conditions trigger.
  - *Why*: Error message changes must not break existing test coverage or mask regressions.
  - *Test*: All 89+ tests pass. `pixi run pytest tests/` green.

---

## Phase 9: CAN Interface Generation

> **Goal**: Generate `can_interface.hpp` and `can_interface.cpp` alongside the existing `can_messages.hpp`, providing a ready-made SocketCAN wrapper with typed dispatch, send helpers, and edge-triggered timeout tracking.

- [x] **9.1 Create golden files** — Write `tests/golden/cpp/can_interface.hpp` and `tests/golden/cpp/can_interface.cpp` by hand based on the spec and `example_schema.yaml`. These define the exact expected output for snapshot tests.
  - *Why*: Golden files must exist before the generator so we have a target to test against.
  - *Details*: For `example_schema.yaml`, the Handlers struct has: `on_drive_status` (data, `plc_to_pc`), no timeout handler for drive_status (no `timeout_ms`). Send overloads for `MotorCommand` and `PcState` (`pc_to_plc`). Timeout tracking: none for the example schema (no `plc_to_pc` messages have `timeout_ms`).
  - *Test*: Files exist and are well-formed C++ (compile check deferred to 9.5).

- [ ] **9.2 Create `can_interface.hpp.j2` template** — Jinja2 template in `can_commsgen/templates/cpp/` producing the header with: pragma once, auto-generated comment, includes, namespace `project_can`, `CanInterface` class declaration with `Handlers` struct (data + timeout handlers for `plc_to_pc` messages), constructor/destructor, `process_frames()`, `wait_readable()`, `send()` overloads for `pc_to_plc` messages, private `compute_filters()`, `check_timeouts()`, `MessageTimeoutState`, pimpl `Impl`.
  - *Why*: Template-driven generation keeps the output consistent with schema changes.
  - *Test*: Template renders without Jinja2 errors (verified in 9.4).

- [ ] **9.3 Create `can_interface.cpp.j2` template** — Jinja2 template producing the implementation with: includes (`poll.h`, `sys/socket.h`, `sys/ioctl.h`, `net/if.h`, `unistd.h`, `cstring`, `stdexcept`), `Impl` struct (socket fd), constructor (socket creation, bind, filter setup), destructor, `process_frames()` (non-blocking read, CAN ID dispatch to `parse_*` + handler, `check_timeouts()`), `wait_readable()` (poll), `send()` overloads (call `build_*`, write to socket), `compute_filters()`, `check_timeouts()`.
  - *Why*: Implementation file contains all SocketCAN system calls and dispatch logic.
  - *Test*: Template renders without Jinja2 errors (verified in 9.4).

- [ ] **9.4 Extend `cpp.py` to generate interface files** — Add generation logic to `generate_cpp()` (or a new `generate_cpp_interface()` function called from the same entrypoint) that renders both templates and writes `can_interface.hpp` and `can_interface.cpp` to the output directory. Prepare template context with: `plc_to_pc` messages (for handlers + timeout tracking), `pc_to_plc` messages (for send overloads), struct names, message names, timeout_ms values.
  - *Why*: Extends the existing C++ generation pipeline without changing schema or PLC modules.
  - *Test*: Snapshot test — generated files match golden files in `tests/golden/cpp/`. Add tests to `tests/test_cpp_gen.py`.

- [ ] **9.5 Verify generated code compiles** — Extend the C++ roundtrip build in `tests/cpp_roundtrip/` to include the generated interface files. Since SocketCAN APIs won't be available in CI, use compile-only checks (or stub the system headers). Update `CMakeLists.txt` to add the interface files as a separate compilation unit or compile-only target.
  - *Why*: Generated C++ must be syntactically valid and type-correct.
  - *Test*: cmake build succeeds (compile-only for interface files). Existing 34 roundtrip tests still pass.

- [ ] **9.6 Update CLI if needed** — Verify that `can_interface.hpp` and `can_interface.cpp` are generated automatically when `--out-cpp` is specified. If `generate_cpp()` was extended (not a separate function), no CLI changes are needed. If a separate function was added, wire it into the CLI pipeline.
  - *Why*: Users should get all C++ files from a single CLI invocation.
  - *Test*: CLI smoke test in `tests/test_cli.py` — verify `can_interface.hpp` and `can_interface.cpp` exist in the output directory after running the CLI.

- [ ] **9.7 Update integration tests** — Extend `tests/test_integration.py` to include the new interface files in the end-to-end snapshot comparison.
  - *Why*: Full pipeline regression coverage must include all generated outputs.
  - *Test*: All integration tests pass, including new interface file comparisons.

---

## Notes

- **Phase ordering**: Rich error messages (Phase 8) should be done first — it's a smaller, self-contained change to `schema.py` and `test_schema.py` only. CAN interface generation (Phase 9) is larger and adds new files across templates, generators, golden files, and tests.
- **No schema model changes needed**: Both specs confirm that the existing normalised model has all the data required. No new dataclass fields or loading logic is needed.
- **Golden file discipline**: Golden files are the source of truth for snapshot tests. Generate → compare byte-for-byte. Fix the generator if there are differences, don't alter golden files.
- **SocketCAN stubs for CI**: The C++ roundtrip environment has a stub `linux/can.h`. Interface generation will need additional stubs for `sys/socket.h`, `poll.h`, etc., or a compile-only target that doesn't link.
- **Template location**: Templates live in `can_commsgen/templates/cpp/`, loaded relative to the package via `__file__`-relative paths (consistent with existing template loading).

# C++ Code Generation

## Problem
Given a normalised schema model, produce the C++ header with enums, structs, bit helpers, and parse/build functions.

## Goal
`can_commsgen/cpp.py` provides a `generate_cpp(schema: Schema, output_dir: Path)` function that writes `can_messages.hpp` to the output directory. A Jinja2 template in `templates/cpp/` defines the format.

## Scope

### Generated file: `can_messages.hpp`
One file containing (in order):
1. Header guard, includes (`cmath`, `cstdint`, `optional`, `linux/can.h`)
2. Namespace `project_can`
3. Enum classes (with explicit backing type)
4. Message structs (real fields as `double`, integers as their C++ type, enums as enum type)
5. `detail::extract_bits` and `detail::insert_bits` inline helpers
6. Parse functions: `parse_{name}(const can_frame&) -> std::optional<StructName>` for EVERY message
7. Build functions: `build_{name}(const StructName&) -> can_frame` for EVERY message

### Key generation rules
- Parse checks CAN ID (masked with CAN_EFF_MASK) and DLC, returns nullopt on mismatch
- Build sets CAN_EFF_FLAG on the ID
- Real fields: parse = `extract_bits * resolution`, build = `std::round(value / resolution)`
- Integer fields: direct static_cast, no scaling
- Bool fields: `extract_bits != 0` for parse, `value ? 1 : 0` for build
- Enum fields: static_cast both directions, always unsigned
- Struct member names use C++ convention: `snake_case_unit`

### NOT in scope
- `can_interface.hpp` / `can_interface.cpp` — deferred to a future loop

## What NOT to change
- Golden files, schema model, design.md

## Testing
- Snapshot test: generate C++ from `tests/fixtures/example_schema.yaml`, compare against `tests/golden/cpp/can_messages.hpp`
- C++ roundtrip test: copy the generated `can_messages.hpp` into `tests/cpp_roundtrip/generated/`, build with cmake, run `test_roundtrip` — all 34 tests must pass
- The pytest suite should orchestrate the C++ roundtrip: generate → copy → cmake build → ctest. Skip if no C++ compiler available.
- Test in `tests/test_cpp_gen.py`

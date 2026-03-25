# can_commsgen

A code generator that takes a single YAML schema and produces both **PLC Structured Text** (IEC 61131-3) and **C++ header-only** code for CAN bus communication -- keeping both sides perfectly in sync from one source of truth.

## The Problem

When a PLC and a PC communicate over CAN, every signal must be implemented twice: once in Structured Text and once in C++. Adding or modifying a single CAN signal means touching 4-6 files across both sides, with scale factors and bit layouts hardcoded independently. This creates drift risk, boilerplate duplication, and subtle bugs.

## The Solution

Define your CAN messages once in YAML. `can_commsgen` generates all the boilerplate:

| Output | Description |
|--------|-------------|
| **PLC Structured Text** | RECV/SEND function blocks, bit-level helpers, GVL, enum types, main input registration |
| **C++ header** | Message structs, `parse_*`/`build_*` functions, bit-level helpers, enums (header-only, no .cpp needed) |
| **Packing report** | Human-readable text showing bit layouts, wire ranges, and physical ranges for review |

Generated files are never edited by hand -- regenerate and commit.

## Quick Start

### Installation

```bash
pip install .            # or: pip install -e ".[dev]" for development
```

Requires **Python 3.11+**.

### Define a Schema

```yaml
version: "1"

plc:
  can_channel: CHAN_0

enums:
  - name: DriveMode
    values:
      IDLE:     0
      VELOCITY: 1
      POSITION: 2
      TORQUE:   3

messages:
  - name: motor_command
    id: 0x00000100
    direction: pc_to_plc
    timeout_ms: 500
    fields:
      - name: target_velocity
        type: real
        min: -3200.0
        max: 3200.0
        resolution: 0.1
        unit: rpm
      - name: torque_limit
        type: real
        min: 0.0
        max: 655.35
        resolution: 0.01
        unit: Nm

  - name: drive_status
    id: 0x00000200
    direction: plc_to_pc
    fields:
      - name: actual_velocity
        type: real
        min: -3200.0
        max: 3200.0
        resolution: 0.1
        unit: rpm
      - name: fault_code
        type: uint8

  - name: pc_state
    id: 0x00000300
    direction: pc_to_plc
    timeout_ms: 1000
    fields:
      - name: drive_mode
        type: DriveMode
```

### Generate Code

```bash
can_commsgen \
  --schema schema.yaml \
  --out-plc generated/plc \
  --out-cpp generated/cpp \
  --out-report generated/packing_report.txt
```

`--schema` is repeatable to merge multiple files. `--out-report` is optional.

### Use the Generated Code

**PLC side** -- call RECV function blocks in your main loop; read values from the GVL:

```pascal
(* In main program *)
MOTOR_COMMAND_RECV(channel := ifmDevice.CAN_CHANNEL.CHAN_0);

(* Use received values *)
myVelocity := GVL.targetVelocity_rpm;
isAlive    := GVL.motorCommandWithinTimeout;
```

**C++ side** -- parse incoming frames, build outgoing ones:

```cpp
#include "can_messages.hpp"

// Parse a received frame
auto msg = can_commsgen::parse_motor_command(frame);
if (msg) {
    std::cout << msg->target_velocity_rpm << " rpm\n";
}

// Build a frame to send
auto frame = can_commsgen::build_drive_status({
    .actual_velocity_rpm = 1500.0,
    .fault_code = 0
});
```

## Schema Reference

### Top-Level

| Property | Required | Description |
|----------|----------|-------------|
| `version` | yes | Schema version, currently `"1"` |
| `plc.can_channel` | yes | ifm `CAN_CHANNEL` enum value (e.g. `CHAN_0`) |
| `enums` | no | List of enum definitions |
| `messages` | yes | List of message definitions |

### Messages

| Property | Required | Description |
|----------|----------|-------------|
| `name` | yes | `snake_case` identifier |
| `id` | yes | 29-bit extended CAN ID (hex, e.g. `0x00000100`) |
| `direction` | yes | `pc_to_plc` or `plc_to_pc` |
| `timeout_ms` | no | Timeout supervision in milliseconds |
| `fields` | yes | Ordered list of signal fields |

**Direction** is defined from the PC's perspective: `pc_to_plc` means the PC sends and the PLC receives.

### Fields

Fields are packed sequentially in big-endian bit order. Offsets are computed automatically.

| Property | Required | Description |
|----------|----------|-------------|
| `name` | yes | `snake_case` identifier |
| `type` | yes | `bool`, `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, `uint64`, `int64`, `real`, or an enum name |
| `min` | for `real` | Minimum physical value |
| `max` | for `real` | Maximum physical value |
| `resolution` | for `real` | Physical value per LSB |
| `unit` | no | Unit suffix (e.g. `rpm`, `degC`, `V`) -- appended to generated variable names |

### Field Types and Wire Encoding

| Type | Wire encoding | Bits |
|------|--------------|------|
| `bool` | 1 bit | 1 |
| Integer (bare) | Full width of type | 8/16/32/64 |
| Integer (with `min`/`max`) | Packed to minimum bits covering range | auto |
| `real` | Fixed-point: `wire_value = round(physical / resolution)` | auto (from min/max/resolution) |
| Enum | Unsigned, `ceil(log2(max_value + 1))` bits | auto |

Real fields use **fixed-point math**, not IEEE floats. The resolution determines the LSB step size. For example, `min: -3200, max: 3200, resolution: 0.1` produces a 16-bit signed wire value ranging from -32000 to 32000.

### Enums

```yaml
enums:
  - name: DriveMode
    values:
      IDLE:     0
      VELOCITY: 1
      POSITION: 2
      TORQUE:   3
```

The backing type is automatically selected as the smallest integer that fits the largest declared value. Reference enums by name in field `type`.

### Validation Rules

The schema validator enforces:

- `real` fields must have `min`, `max`, and `resolution`
- `resolution` only allowed on `real` fields
- `min`/`max` not allowed on `bool` or enum fields
- Integer `min`/`max` must fit within the endpoint type's range
- Unsigned types cannot have `min < 0`
- Total message bits must not exceed 64
- CAN IDs must be unique across all messages
- Enum references must match a declared enum name

## Generated Output Details

### PLC Files

For each schema, the following files are generated in the PLC output directory:

| File | Purpose |
|------|---------|
| `CAN_EXTRACT_BITS.st` | Helper: extract N bits from a byte array at a bit offset |
| `CAN_INSERT_BITS.st` | Helper: insert N bits into a byte array at a bit offset |
| `GVL.st` | Global Variable List for received message fields + timeout booleans |
| `main_input.st` | Calls all RECV function blocks with the configured CAN channel |
| `{MESSAGE}_RECV.st` | One per `pc_to_plc` message -- receives, unpacks, tracks timeout |
| `{MESSAGE}_SEND.st` | One per `plc_to_pc` message -- packs and transmits |
| `{EnumName}.st` | One per enum type |

All files begin with `(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)`.

RECV function blocks use ifm's `ifmRCAN.CAN_Rx` and write unpacked values into the GVL. SEND function blocks take field values as `VAR_INPUT` (they do not read from the GVL).

### C++ Header

A single `can_messages.hpp` is generated in the `can_commsgen` namespace containing:

- **Enums** with explicit backing types (`enum class DriveMode : uint8_t`)
- **Structs** with `double` for real fields, native C++ types for integers
- **`parse_*` functions** -- take a `can_frame`, return `std::optional<Struct>` (checks ID and DLC)
- **`build_*` functions** -- take a struct, return a `can_frame` with `CAN_EFF_FLAG` set
- **Inline bit helpers** in the `detail` namespace

Parse and build functions are generated for every message regardless of direction, so both sides can encode and decode.

### Packing Report

An optional text report showing the bit layout of every message:

```
can_commsgen packing report
Schema: schema.yaml

================================================================================
motor_command  (0x00000100, pc_to_plc, timeout 500ms)
  DLC: 4 bytes (32 bits used / 64 max)
--------------------------------------------------------------------------------
  Bit offset  Bits  Signed  Field               Wire range        Physical range        Resolution
  0           16    yes     target_velocity      [-32000, 32000]   [-3200.0, 3200.0] rpm 0.1
  16          16    no      torque_limit         [0, 65535]        [0.0, 655.35] Nm      0.01
================================================================================
```

## How It Works

1. **Load & validate** -- YAML is parsed with PyYAML and validated against a JSON Schema. Dataclass models are constructed for each message, field, and enum.

2. **Wire type inference** -- For each field, the generator computes the wire bit width, signedness, and offset. Real fields are converted to fixed-point ranges; integers are packed to minimum bits; enums derive width from their max value.

3. **Template rendering** -- Jinja2 templates produce the output files. Each template receives the validated schema model and renders deterministic output (same schema always produces identical files).

4. **Output** -- Files are written to the specified output directories. The CLI handles multi-schema merging by combining messages and enums before generation.

## Development

### Setup

```bash
git clone <repo-url>
cd can_commsgen
pip install -e ".[dev]"
```

Or with Nix (provides Python, pixi, CMake, GCC):

```bash
nix develop    # or use direnv with: direnv allow
pixi install
```

### Quality Gates

Run in this order:

```bash
pixi run ruff check can_commsgen/ tests/    # Lint
pixi run pyright can_commsgen/              # Type check
pixi run pytest tests/                      # Tests (Python + C++ roundtrip)
```

### Tests

| Test file | What it covers |
|-----------|---------------|
| `test_schema.py` | Wire type inference, validation rules, naming conventions |
| `test_plc_gen.py` | PLC output snapshot tests against golden files |
| `test_cpp_gen.py` | C++ output snapshot tests against golden files |
| `test_report_gen.py` | Packing report snapshot test |
| `test_cli.py` | CLI smoke tests and error handling |
| `test_integration.py` | End-to-end generation and multi-schema merge |

A **C++ roundtrip test** in `tests/cpp_roundtrip/` compiles the generated header and runs 34 parse/build roundtrip tests to verify bitpacking correctness:

```bash
cd tests/cpp_roundtrip
cmake -B build && cmake --build build && ctest --output-on-failure
```

### Project Structure

```
can_commsgen/
├── can_commsgen/
│   ├── cli.py              # Click CLI entrypoint
│   ├── schema.py           # YAML loading, validation, wire type inference
│   ├── plc.py              # PLC Structured Text generation
│   ├── cpp.py              # C++ header generation
│   ├── report.py           # Packing report generation
│   └── templates/
│       ├── plc/            # 7 Jinja2 templates for ST files
│       └── cpp/            # 1 Jinja2 template for the C++ header
├── tests/
│   ├── fixtures/           # Example YAML schemas
│   ├── golden/             # Expected outputs for snapshot tests
│   └── cpp_roundtrip/      # C++ compilation + roundtrip tests
├── schema.json             # JSON Schema for YAML validation
├── pyproject.toml
└── design.md               # Authoritative design document
```

## License

See [LICENSE](LICENSE) for details.

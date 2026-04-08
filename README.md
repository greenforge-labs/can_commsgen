# can_commsgen

A code generator that takes a single YAML schema and produces both **PLC Structured Text** (IEC 61131-3) and **C++ header + SocketCAN interface** code for CAN bus communication -- keeping both sides perfectly in sync from one source of truth.

## The Problem

When a PLC and a PC communicate over CAN, every signal must be implemented twice: once in Structured Text and once in C++. Adding or modifying a single CAN signal means touching multiple files across both sides, with scale factors and bit layouts hardcoded independently. This creates drift risk, boilerplate duplication, and subtle bugs.

## The Solution

Define your CAN messages once in YAML. `can_commsgen` generates all the boilerplate:

| Output | Description |
|--------|-------------|
| **PLC Structured Text** | RECV/SEND function blocks, bit-level helpers, GVL, enum types, main input registration |
| **C++ header** | Message structs, `parse_*`/`build_*` functions, bit-level helpers, enums (header-only, no .cpp needed) |
| **C++ CanInterface** | SocketCAN class with typed `send()` overloads, receive-dispatch via handlers, and hardware CAN filters |
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
      - name: motor_temp
        type: real
        min: -40.0
        max: 200.0
        resolution: 0.1
        unit: degC
      - name: bus_voltage
        type: real
        min: 0.0
        max: 102.3
        resolution: 0.1
        unit: V
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

**PLC side** -- the generated `main_input.st` calls all RECV function blocks for you. Read received values from the GVL and call SEND function blocks to transmit:

```pascal
(* main_input.st is auto-generated and calls all RECV FBs.
   Just add it to your PLC program -- no manual wiring needed. *)

(* Read received values from the GVL *)
myVelocity := GVL.targetVelocity_rpm;
isAlive    := GVL.motorCommandWithinTimeout;

(* Send a message *)
DRIVE_STATUS_SEND(
    channel          := ifmDevice.CAN_CHANNEL.CHAN_0,
    actualVelocity_rpm := myVelocity,
    motorTemp_degC     := tempSensor,
    busVoltage_V       := voltage,
    faultCode          := 0
);
```

If your PLC project already uses a different GVL name, set `gvl_name` in the schema to match:

```yaml
plc:
  can_channel: CHAN_0
  gvl_name: PC_INTERFACE_OUT   # output file becomes PC_INTERFACE_OUT.st
```

**C++ side (low-level)** -- parse incoming frames, build outgoing ones:

```cpp
#include "can_messages.hpp"

// Parse a received frame
auto msg = project_can::parse_drive_status(frame);
if (msg) {
    std::cout << msg->actual_velocity_rpm << " rpm\n";
    std::cout << msg->motor_temp_degC << " degC\n";
}

// Build a frame to send
auto frame = project_can::build_motor_command({
    .target_velocity_rpm = 1500.0,
    .torque_limit_Nm = 25.0
});
```

**C++ side (CanInterface)** -- typed send/receive with SocketCAN:

```cpp
#include "can_interface.hpp"

project_can::CanInterface can("can0", {
    .on_drive_status = [](project_can::DriveStatus status) {
        std::cout << status.actual_velocity_rpm << " rpm, "
                  << status.motor_temp_degC << " degC\n";
    }
});

// Send a message (type-safe overloads)
can.send(project_can::MotorCommand{
    .target_velocity_rpm = 1500.0,
    .torque_limit_Nm = 25.0
});

// Process incoming frames (parses + dispatches to handlers)
can.wait_readable();
can.process_frames();
```

## Schema Reference

### Top-Level

| Property | Required | Description |
|----------|----------|-------------|
| `version` | yes | Schema version, currently `"1"` |
| `plc.can_channel` | yes | ifm `CAN_CHANNEL` enum value (e.g. `CHAN_0`) |
| `plc.gvl_name` | no | Name of the generated Global Variable List (default `GVL`). Controls the output filename and the qualifier prefix in RECV function blocks. |
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

Fields are packed sequentially in little-endian bit order. Offsets are computed automatically.

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
| `{gvl_name}.st` | Global Variable List for received message fields + timeout booleans (default `GVL.st`) |
| `main_input.st` | Calls all RECV function blocks with the configured CAN channel |
| `{MESSAGE}_RECV.st` | One per `pc_to_plc` message -- receives, unpacks, tracks timeout |
| `{MESSAGE}_SEND.st` | One per `plc_to_pc` message -- packs and transmits |
| `{EnumName}.st` | One per enum type |

All files begin with `(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)`.

RECV function blocks use ifm's `ifmRCAN.CAN_Rx` and write unpacked values into the GVL. SEND function blocks take field values as `VAR_INPUT` (they do not read from the GVL).

### C++ Files

Three files are generated in the C++ output directory, all under the `project_can` namespace:

| File | Purpose |
|------|---------|
| `can_messages.hpp` | Header-only: enums, message structs, `parse_*`/`build_*` functions, bit helpers |
| `can_interface.hpp` | `CanInterface` class declaration with typed send/receive API |
| `can_interface.cpp` | `CanInterface` implementation: SocketCAN socket, frame dispatch, CAN filters |

**can_messages.hpp** contains:

- **Enums** with explicit backing types (`enum class DriveMode : uint8_t`)
- **Structs** with `double` for real fields, native C++ types for integers
- **`parse_*` functions** -- take a `can_frame`, return `std::optional<Struct>` (checks ID and DLC)
- **`build_*` functions** -- take a struct, return a `can_frame` with `CAN_EFF_FLAG` set
- **Inline bit helpers** (`extract_bits`/`insert_bits`) in the `detail` namespace

Parse and build functions are generated for every message regardless of direction, so both sides can encode and decode.

**CanInterface** provides a higher-level API:

- Constructor takes a SocketCAN device name (e.g. `"can0"`) and a `Handlers` struct with `std::function` callbacks for each `plc_to_pc` message
- Type-safe `send()` overloads for each `pc_to_plc` message
- `process_frames()` reads from the socket, parses frames, and dispatches to the appropriate handler
- `wait_readable()` blocks until data is available on the socket
- Hardware CAN filters are auto-configured based on which handlers are set
- Move-only semantics (non-copyable)

### Packing Report

An optional text report showing the bit layout of every message:

```
can_commsgen packing report
Schema: schema.yaml

================================================================================
motor_command  (0x00000100, pc_to_plc, timeout 500ms)
  DLC: 4 bytes (32 bits used / 64 max)
--------------------------------------------------------------------------------
  Bit offset  Bits  Signed  Field               Type   Wire range          Physical range          Resolution
  0           16    yes     target_velocity      real   [-32000, 32000]     [-3200.0, 3200.0] rpm   0.1
  16          16    no      torque_limit         real   [0, 65535]          [0.0, 655.35] Nm        0.01
================================================================================

================================================================================
drive_status  (0x00000200, plc_to_pc)
  DLC: 6 bytes (46 bits used / 64 max)
--------------------------------------------------------------------------------
  Bit offset  Bits  Signed  Field               Type   Wire range          Physical range          Resolution
  0           16    yes     actual_velocity      real   [-32000, 32000]     [-3200.0, 3200.0] rpm   0.1
  16          12    yes     motor_temp           real   [-400, 2000]        [-40.0, 200.0] degC     0.1
  28          10    no      bus_voltage          real   [0, 1023]           [0.0, 102.3] V          0.1
  38          8     no      fault_code           uint8  [0, 255]            --                      --
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
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Requires **Python 3.11+**.

### Quality Gates

Run in this order:

```bash
pre-commit run --all-files            # Formatting & linting
pyright can_commsgen/                 # Type check
pytest tests/                         # Tests (Python + C++ roundtrip)
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

A **C++ roundtrip test** in `tests/cpp_tests/` compiles the generated header and runs parse/build roundtrip tests to verify bitpacking correctness:

```bash
cd tests/cpp_tests
cmake -B build && cmake --build build && ctest --output-on-failure
```

A separate **CanInterface test** in the same directory verifies socket setup, handler dispatch, and CAN filter construction.

### Project Structure

```
can_commsgen/
├── can_commsgen/
│   ├── cli.py              # Click CLI entrypoint
│   ├── schema.py           # YAML loading, validation, wire type inference
│   ├── plc.py              # PLC Structured Text generation
│   ├── cpp.py              # C++ header + interface generation
│   ├── report.py           # Packing report generation
│   └── templates/
│       ├── plc/            # 7 Jinja2 templates for ST files
│       └── cpp/            # 3 Jinja2 templates (messages header, interface header + impl)
├── tests/
│   ├── fixtures/           # Example YAML schemas
│   ├── golden/             # Expected outputs for snapshot tests
│   │   ├── plc/            # 8 golden PLC files
│   │   ├── cpp/            # 3 golden C++ files
│   │   └── report/         # 1 golden packing report
│   └── cpp_tests/          # C++ compilation + roundtrip tests
├── schema.json             # JSON Schema for YAML validation
├── pyproject.toml
└── design.md               # Authoritative design document
```

## License

See [LICENSE](LICENSE) for details.

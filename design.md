# can_commsgen — Design Document

## 1. Motivation

CAN-based PLC-PC communication layers require maintaining parallel implementations in two
languages (IEC 61131-3 Structured Text and C++) that must stay in sync. Adding or
modifying a single signal means touching 4–6 files across both sides, with scale factors
hardcoded independently in each. This creates drift risk and significant boilerplate.

`can_commsgen` takes a single YAML schema as the source of truth and produces:
- All PLC Structured Text boilerplate (function blocks, GVL declarations, main input registration)
- All C++ boilerplate (message structs, CAN interface class)

Hand-written code on both sides calls into the generated layer. The generated files are
never edited manually — regenerate and commit.

---

## 2. Schema Format

Schema files are YAML. A project may have one schema file or split across multiple
(e.g. per subsystem); the generator accepts a list of inputs.

### 2.1 Top-level structure

```yaml
version: "1"

plc:
  can_channel: CHAN_0             # ifm CAN_CHANNEL enum value

enums:
  - ...

messages:
  - ...
```

#### `plc` section

| Property | Required | Description |
|----------|----------|-------------|
| `can_channel` | yes | ifm `CAN_CHANNEL` enum value (e.g. `CHAN_0`, `CHAN_1`). Used in generated `main_input.st` and SEND FBs. |

### 2.2 Enums

Enums are declared once and referenced by name in message fields. The generator emits
the enum in both ST (`.st` file) and C++ (in the generated header).

```yaml
enums:
  - name: DriveMode
    values:
      IDLE:     0
      VELOCITY: 1
      POSITION: 2
      TORQUE:   3
```

The generator derives two things from the declared values:

- **Wire bit width:** `ceil(log2(max_value + 1))`. DriveMode (max 3) packs to 2 bits.
- **Endpoint backing type:** the smallest standard integer that fits all values.
  Max 0-255 → `uint8_t` / `USINT`, max 256-65535 → `uint16_t` / `UINT`, etc.
  C++ emits `enum class DriveMode : uint8_t { ... }`;
  PLC emits `TYPE DriveMode : (...) USINT; END_TYPE`.

### 2.3 Messages

```yaml
messages:
  - name: motor_command          # snake_case; drives all generated identifiers
    id: 0x00000100               # 29-bit extended CAN ID (hex)
    direction: pc_to_plc         # pc_to_plc | plc_to_pc
    timeout_ms: 500              # optional; omit for messages with no timeout
    fields:
      - ...
```

`direction` is from the PC's perspective:
- `pc_to_plc` — PC sends, PLC receives (RX on PLC side, TX on C++ side)
- `plc_to_pc` — PLC sends, PC receives (TX on PLC side, RX on C++ side)

Each CAN ID has exactly one producer — a message cannot be bidirectional. The
generator enforces this: duplicate CAN IDs across messages are always an error,
regardless of direction.

### 2.4 Fields

Fields are packed sequentially from bit 0 of the frame (MSB-first within each field,
big-endian byte order). Bit offsets are inferred; the generator bitpacks fields to the
minimum number of bits required by their wire range.

Every field has a `type` that describes the **endpoint type** — the type seen by
application code on both sides (PLC variable type, C++ struct member type).

#### Field properties

| Property | Required | Description |
|----------|----------|-------------|
| `name` | always | Snake_case field name. Drives all generated identifiers (see naming below). |
| `type` | always | Endpoint type: integer type, `real`, `bool`, or an enum name (see table below). |
| `min` | `real`: yes, integer: optional, `bool`/enum: no | Minimum physical value (inclusive). Must be provided together with `max`. |
| `max` | `real`: yes, integer: optional, `bool`/enum: no | Maximum physical value (inclusive). Must be provided together with `min`. |
| `resolution` | `real`: yes, all others: no | Physical value per LSB. Only valid on `real` fields. |
| `unit` | no | Unit suffix string (e.g. `rpm`, `degC`, `rad_s`). Appended to generated variable names. |

#### Generated variable names

Variable names are derived from `name` and `unit` automatically — there is no
separate `plc_var` property.

- **PLC:** `camelCase` + `_unit` suffix (per PLC style guide). E.g. `target_velocity` + `rpm` → `targetVelocity_rpm`
- **C++:** `snake_case` + `_unit` suffix. E.g. `target_velocity` + `rpm` → `target_velocity_rpm`

Fields without a `unit` use the name alone: `fault_code` → PLC `faultCode`, C++ `fault_code`.

Unit suffixes should use shorthand that avoids special characters (e.g. `ms2` for m/s²,
`rad_s` for rad/s).

#### Valid endpoint types

| Type | PLC type | C++ type |
|------|----------|----------|
| `bool` | `BOOL` | `bool` |
| `uint8` | `USINT` | `uint8_t` |
| `int8` | `SINT` | `int8_t` |
| `uint16` | `UINT` | `uint16_t` |
| `int16` | `INT` | `int16_t` |
| `uint32` | `UDINT` | `uint32_t` |
| `int32` | `DINT` | `int32_t` |
| `uint64` | `ULINT` | `uint64_t` |
| `int64` | `LINT` | `int64_t` |
| `real` | `REAL` | `double` |
| *EnumName* | *EnumName* | *EnumName* |

#### Wire type inference

The wire bit width is derived from the endpoint type and optional constraints.
Signedness comes from the declared type, not inferred from min/max (though the
generator validates they are consistent):

| Endpoint type | min/max | resolution | Wire behaviour |
|---|---|---|---|
| `real` | **required** | **required** | Scaled to integer on wire (see below) |
| Integer | provided | — | Packed to minimum bits covering `[min, max]` |
| Integer | omitted | — | Full width of the type (no packing) |
| `bool` | — | — | 1 bit |
| Enum name | — | — | Minimum bits to represent enum's max value |

#### Resolution and real-valued fields

`resolution` is the physical value that one LSB (least significant bit) represents on
the wire. Real-valued fields use fixed-point representation: scaled to integers for
packing and scaled back on the receiving side. This is a deliberate choice over IEEE
floats on the wire — fixed-point allows bitpacking to arbitrary widths and gives uniform
precision across the full range.

The conversion:

```
wire_value     = round(physical_value / resolution)
physical_value = wire_value * resolution
```

For example, a velocity field with `resolution: 0.1` and `unit: rpm` means each wire
count is 0.1 rpm. A physical value of 123.4 rpm is transmitted as wire value 1234.

#### Wire bit calculation

Given a field's wire range, the generator computes the minimum number of bits needed.
Signedness is known from the endpoint type (signed types: `int8`, `int16`, `int32`,
`int64`; for `real` fields, signed if `min < 0`).

1. **Determine the wire range** from the schema constraints:
   - `real` field: `wire_min = round(min / resolution)`, `wire_max = round(max / resolution)`
   - Integer field with `min`/`max`: `wire_min = min`, `wire_max = max`
   - Integer field without `min`/`max`: full width of the endpoint type, no further inference
   - `bool`: fixed at 1 bit
   - Enum: `wire_min = 0`, `wire_max = max declared enum value`

2. **Validate consistency** between the declared type and the wire range:
   - Unsigned type with `min < 0` → error
   - `wire_max` exceeds the endpoint type's maximum → error
   - `wire_min` below the endpoint type's minimum → error

3. **Compute bit width:**
   - Unsigned: `bits = ceil(log2(wire_max + 1))`
   - Signed: `bits = 1 + ceil(log2(max(abs(wire_min), abs(wire_max)) + 1))`
     (1 sign bit + enough magnitude bits for the largest absolute value)

**Worked example** — `target_velocity`:
```
type: real, min: -3200.0, max: 3200.0, resolution: 0.1

wire_min = round(-3200.0 / 0.1) = -32000
wire_max = round( 3200.0 / 0.1) =  32000
signed   = true  (type is real and min < 0)
bits     = 1 + ceil(log2(32000 + 1)) = 1 + 15 = 16
```

#### Field examples

```yaml
fields:
  # real endpoint — wire type inferred from min/max/resolution
  - name: target_velocity
    type: real
    min: -3200.0
    max: 3200.0
    resolution: 0.1
    unit: rpm
    # → PLC: targetVelocity_rpm (REAL), C++: target_velocity_rpm (double)
    # → wire: signed, 16 bits [-32000, 32000]

  # integer with range — bitpacked on wire
  - name: bus_voltage_raw
    type: uint16
    min: 0
    max: 1023
    unit: V
    # → PLC: busVoltageRaw_V (UINT), C++: bus_voltage_raw_V (uint16_t)
    # → wire: unsigned, 10 bits

  # plain integer — full width, direct cast
  - name: fault_code
    type: uint8
    # → PLC: faultCode (USINT), C++: fault_code (uint8_t)
    # → wire: 8 bits, no conversion

  # enum — wire bits from max declared value
  - name: drive_mode
    type: DriveMode
    # → PLC: driveMode (DriveMode), C++: drive_mode (DriveMode)
    # → wire: 2 bits (max value 3)

  # bool
  - name: estop_active
    type: bool
    # → PLC: estopActive (BOOL), C++: estop_active (bool)
    # → wire: 1 bit
```

Field order in the YAML defines wire order — fields are packed sequentially with no
gaps.

### 2.5 Validation rules for field type + constraints

- `type: real` **must** have `min`, `max`, and `resolution`. Error if any are missing.
- Integer types **may** have `min` and `max` (both or neither). When present, the
  generator validates that `[min, max]` fits within the endpoint type's range.
- `resolution` is **only** valid on `type: real`. Error if used with integer or enum types.
- `bool` and enum types **must not** have `min`, `max`, or `resolution`.
- The total packed frame size must not exceed 64 bits (CAN max 8 bytes).

### 2.6 Full example

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

---

## 3. Generated PLC Output

All generated files have a header comment:
```
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
(* Source: schema/*.yaml *)
```

### 3.1 Enums

One file per enum: `{EnumName}.st`

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE DriveMode : (
    IDLE     := 0,
    VELOCITY := 1,
    POSITION := 2,
    TORQUE   := 3
) USINT;   (* smallest IEC type fitting max value 3; wire-packed to 2 bits *)
END_TYPE
```

`qualified_only` requires values to be referenced as `DriveMode.VELOCITY` (not bare
`VELOCITY`), preventing namespace collisions. `strict` prevents implicit integer-to-enum
casts.

### 3.2 ifm library dependency

The generated PLC code uses the ifm `ifmRCAN` library directly:

- **RECV FBs** each embed an `ifmRCAN.CAN_Rx` instance filtered to the message's CAN ID
- **SEND FBs** each embed an `ifmRCAN.CAN_Tx` instance
- Both take `eChannel : ifmDevice.CAN_CHANNEL` as `VAR_INPUT`

This is ifm-specific by design. If a different PLC platform is needed in the future,
the templates can be swapped without changing the schema or generator logic.

### 3.3 Bit-level pack/unpack helpers

The generator emits two helper functions used by all RECV and SEND FBs:

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION CAN_EXTRACT_BITS : LINT
VAR_INPUT
    data      : ARRAY[0..7] OF USINT;
    bitOffset : UINT;
    bitCount  : UINT;
    signed    : BOOL;
END_VAR
```

Extracts `bitCount` bits starting at `bitOffset` from the data array, returning
the value as `LINT`. When `signed` is `TRUE`, the value is sign-extended. Generated
RECV FBs call this and cast the result to the appropriate endpoint type.

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION CAN_INSERT_BITS : BOOL
VAR_INPUT
    value     : LINT;
    bitOffset : UINT;
    bitCount  : UINT;
END_VAR
VAR_IN_OUT
    data      : ARRAY[0..7] OF USINT;
END_VAR
```

Inserts the low `bitCount` bits of `value` into the data array at `bitOffset`.
Generated SEND FBs call this for each field.

### 3.4 Per-message function blocks

One FB per message: `{MSG_NAME_UPPER}_RECV.st` (for `pc_to_plc`) or
`{MSG_NAME_UPPER}_SEND.st` (for `plc_to_pc`).

**RECV FB** (pc_to_plc, runs on PLC receive):

Each RECV FB embeds its own `ifmRCAN.CAN_Rx` instance filtered to the message's CAN ID.
It receives independently, unpacks fields into the GVL, and manages its own timeout.

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION_BLOCK MOTOR_COMMAND_RECV
VAR_INPUT
    channel : ifmDevice.CAN_CHANNEL;
END_VAR
VAR
    rx          : ifmRCAN.CAN_Rx;
    timer       : TON;
    rxData      : ARRAY[0..7] OF USINT;
END_VAR

rx(xEnable := TRUE, eChannel := channel, xExtended := TRUE, udiID := 16#00000100);

IF rx.uiAvailable > 0 AND rx.usiDLC = 4 THEN
    rxData := rx.aData;
    GVL.targetVelocity_rpm  := TO_REAL(CAN_EXTRACT_BITS(rxData, 0, 16, TRUE)) * 0.1;
    GVL.torqueLimit_Nm      := TO_REAL(CAN_EXTRACT_BITS(rxData, 16, 16, FALSE)) * 0.01;
    timer(IN := FALSE);
END_IF

timer(IN := TRUE, PT := T#500ms);
GVL.motorCommandWithinTimeout := NOT timer.Q;
```

**SEND FB** (plc_to_pc, called by user code):

SEND FBs take field values as `VAR_INPUT` and transmit directly via an internal
`ifmRCAN.CAN_Tx` instance. They do not read from the GVL — the caller passes values
from wherever they live (hardware modules, control logic, etc.).

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION_BLOCK DRIVE_STATUS_SEND
VAR_INPUT
    channel             : ifmDevice.CAN_CHANNEL;
    actualVelocity_rpm  : REAL;
    motorTemp_degC      : REAL;
    busVoltage_V        : REAL;
    faultCode           : USINT;
END_VAR
VAR
    tx   : ifmRCAN.CAN_Tx;
    data : ARRAY[0..7] OF USINT;
END_VAR

data := [8(0)];
CAN_INSERT_BITS(TO_LINT(REAL_TO_INT(actualVelocity_rpm / 0.1)), 0, 16, data);
CAN_INSERT_BITS(TO_LINT(REAL_TO_INT(motorTemp_degC / 0.1)),     16, 12, data);
CAN_INSERT_BITS(TO_LINT(REAL_TO_UINT(busVoltage_V / 0.1)),      28, 10, data);
CAN_INSERT_BITS(TO_LINT(faultCode),                              38, 8,  data);

tx(xEnable := TRUE, eChannel := channel, xExtended := TRUE,
   udiID := 16#00000200, usiDLC := 6, aData := data);
```

### 3.5 Global variable list

`GVL.st` — contains variables for **received** (`pc_to_plc`) message fields and their
timeout booleans. Outgoing (`plc_to_pc`) message fields are **not** included — SEND FBs
take their values as `VAR_INPUT`, so the caller decides where those values come from.

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
{attribute 'qualified_only'}
VAR_GLOBAL
    (* motor_command — 0x00000100, pc_to_plc *)
    targetVelocity_rpm              : REAL;    (* real, [-3200.0, 3200.0], res 0.1 *)
    torqueLimit_Nm                  : REAL;    (* real, [0.0, 655.35], res 0.01 *)
    motorCommandWithinTimeout       : BOOL;

    (* pc_state — 0x00000300, pc_to_plc *)
    driveMode                       : DriveMode;
    pcStateWithinTimeout            : BOOL;
END_VAR
```

The `qualified_only` attribute requires all references to use the `GVL.` prefix
(e.g. `GVL.targetVelocity_rpm`), preventing namespace collisions with user-defined
variables.

### 3.6 Main input registration

`main_input.st` — calls all RECV FBs (`pc_to_plc` messages), passing the CAN channel
from the schema's `plc.can_channel` setting:

```pascal
(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
MOTOR_COMMAND_RECV(channel := ifmDevice.CAN_CHANNEL.CHAN_0);
PC_STATE_RECV(channel := ifmDevice.CAN_CHANNEL.CHAN_0);
```

There is no generated `main_output.st`. The user calls SEND FBs from their own code,
passing the channel, field values, and controlling send rate as needed.

---

## 4. Generated C++ Output

All generated files have a header comment:
```cpp
// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
// Source: schema/*.yaml
```

### 4.1 Enums and message structs (`can_messages.hpp`)

One struct per message, with real-world-unit `double` fields. Parse returns
`std::optional` (nullopt on ID or DLC mismatch). Build takes a const struct ref.

```cpp
// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#pragma once
#include <cstdint>
#include <optional>
#include <linux/can.h>

namespace project_can {

// ── Enums ────────────────────────────────────────────────────────────────────

enum class DriveMode : uint8_t {
    IDLE     = 0,
    VELOCITY = 1,
    POSITION = 2,
    TORQUE   = 3,
};

// ── Message structs ──────────────────────────────────────────────────────────

// motor_command (0x00000100, pc_to_plc)
struct MotorCommand {
    double target_velocity_rpm;   // [-3200.0, 3200.0], res 0.1
    double torque_limit_Nm;       // [0.0, 655.35], res 0.01
};

// drive_status (0x00000200, plc_to_pc)
struct DriveStatus {
    double actual_velocity_rpm;   // [-3200.0, 3200.0], res 0.1
    double motor_temp_degC;       // [-40.0, 200.0], res 0.1
    double bus_voltage_V;         // [0.0, 102.3], res 0.1
    uint8_t fault_code;
};

// pc_state (0x00000300, pc_to_plc)
struct PcState {
    DriveMode drive_mode;
};

} // namespace project_can
```

### 4.2 Bit-level pack/unpack helpers

The generated header includes inline helper functions analogous to the PLC's
`CAN_EXTRACT_BITS` / `CAN_INSERT_BITS` (section 3.3). These are used by the
parse and build functions below.

```cpp
namespace detail {

inline int64_t extract_bits(const uint8_t data[8], uint16_t bit_offset,
                            uint16_t bit_count, bool is_signed) {
    uint64_t raw = 0;
    for (uint16_t i = 0; i < bit_count; ++i) {
        uint16_t byte_idx = (bit_offset + i) / 8;
        uint16_t bit_idx  = (bit_offset + i) % 8;
        if (data[byte_idx] & (1u << bit_idx))
            raw |= (uint64_t{1} << i);
    }
    if (is_signed && (raw & (uint64_t{1} << (bit_count - 1)))) {
        raw |= ~((uint64_t{1} << bit_count) - 1);  // sign-extend
    }
    return static_cast<int64_t>(raw);
}

inline void insert_bits(uint8_t data[8], uint16_t bit_offset,
                        uint16_t bit_count, int64_t value) {
    auto raw = static_cast<uint64_t>(value);
    for (uint16_t i = 0; i < bit_count; ++i) {
        uint16_t byte_idx = (bit_offset + i) / 8;
        uint16_t bit_idx  = (bit_offset + i) % 8;
        if (raw & (uint64_t{1} << i))
            data[byte_idx] |= (1u << bit_idx);
        else
            data[byte_idx] &= ~(1u << bit_idx);
    }
}

} // namespace detail
```

### 4.3 Parse and build functions

Each message gets a `parse_*` function (returns `std::optional`, nullopt on ID
or DLC mismatch) and a `build_*` function (returns a `can_frame`). These mirror
the PLC's RECV and SEND function blocks (section 3.4) and apply the same wire
type inference rules from section 2.4.

The conversion logic per field type:

| Field type | Parse (wire → endpoint) | Build (endpoint → wire) |
|---|---|---|
| `real` | `extract_bits(signed) * resolution` → `double` | `std::round(value / resolution)` → `insert_bits` |
| Integer with min/max | `extract_bits(signed)` → cast to endpoint type | cast to `int64_t` → `insert_bits` |
| Integer (full width) | `extract_bits(signed)` → cast to endpoint type | cast to `int64_t` → `insert_bits` |
| `bool` | `extract_bits(1 bit) != 0` | `value ? 1 : 0` → `insert_bits` |
| Enum | `static_cast<EnumType>(extract_bits(unsigned))` | `static_cast<int64_t>(value)` → `insert_bits` |

```cpp
// ── Parse functions (wire → struct) ─────────────────────────────────────────

// drive_status (0x00000200, plc_to_pc)
inline std::optional<DriveStatus> parse_drive_status(const can_frame &frame) {
    if ((frame.can_id & CAN_EFF_MASK) != 0x00000200) return std::nullopt;
    if (frame.can_dlc != 6) return std::nullopt;

    DriveStatus msg;
    //                                          offset  bits  signed
    msg.actual_velocity_rpm = detail::extract_bits(frame.data, 0,  16, true)  * 0.1;
    msg.motor_temp_degC     = detail::extract_bits(frame.data, 16, 12, true)  * 0.1;
    msg.bus_voltage_V       = detail::extract_bits(frame.data, 28, 10, false) * 0.1;
    msg.fault_code          = static_cast<uint8_t>(
                              detail::extract_bits(frame.data, 38, 8,  false));
    return msg;
}

// pc_state (0x00000300, pc_to_plc)
inline std::optional<PcState> parse_pc_state(const can_frame &frame) {
    if ((frame.can_id & CAN_EFF_MASK) != 0x00000300) return std::nullopt;
    if (frame.can_dlc != 1) return std::nullopt;

    PcState msg;
    msg.drive_mode = static_cast<DriveMode>(
                     detail::extract_bits(frame.data, 0, 2, false));
    return msg;
}

// ── Build functions (struct → wire) ─────────────────────────────────────────

// motor_command (0x00000100, pc_to_plc)
inline can_frame build_motor_command(const MotorCommand &msg) {
    can_frame frame{};
    frame.can_id  = 0x00000100 | CAN_EFF_FLAG;
    frame.can_dlc = 4;

    //                                        offset  bits  value
    detail::insert_bits(frame.data, 0,  16, static_cast<int64_t>(std::round(msg.target_velocity_rpm / 0.1)));
    detail::insert_bits(frame.data, 16, 16, static_cast<int64_t>(std::round(msg.torque_limit_Nm / 0.01)));
    return frame;
}

// pc_state (0x00000300, pc_to_plc)
inline can_frame build_pc_state(const PcState &msg) {
    can_frame frame{};
    frame.can_id  = 0x00000300 | CAN_EFF_FLAG;
    frame.can_dlc = 1;

    detail::insert_bits(frame.data, 0, 2, static_cast<int64_t>(msg.drive_mode));
    return frame;
}
```

**Correspondence with PLC pack/unpack:**
- `extract_bits` with `is_signed=true` is equivalent to ST's `CAN_EXTRACT_BITS(..., signed := TRUE)` — both sign-extend from the packed bit width.
- Real field parse: `extract_bits(...) * resolution` mirrors ST's `TO_REAL(CAN_EXTRACT_BITS(...)) * resolution`.
- Real field build: `std::round(value / resolution)` mirrors ST's `REAL_TO_INT(value / resolution)` (signed) or `REAL_TO_UINT(value / resolution)` (unsigned).
- Integer fields: direct cast, no scaling — same as ST's `TO_LINT(fieldName)` on send and cast-from-`LINT` on receive.
- Enum fields: `static_cast<EnumType>(extract_bits(..., false))` mirrors ST's cast from `LINT` to the enum type; build uses `static_cast<int64_t>(value)` matching ST's `TO_LINT(driveMode)`.
- Bool fields: `extract_bits(1 bit) != 0` mirrors ST's 1-bit extract with implicit bool conversion.

### 4.4 CAN interface (`can_interface.hpp` / `can_interface.cpp`)

```cpp
// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#pragma once
#include <chrono>
#include <functional>
#include <string>
#include <linux/can.h>
#include "can_messages.hpp"

namespace project_can {

class CanInterface {
public:
    struct Handlers {
        // plc_to_pc — one data handler and one timeout handler per message.
        // Both are independently optional. A message is added to the socket
        // filter if *either* handler is non-null.
        //
        // on_*          — called on every received frame (data dispatch)
        // on_*_timeout  — called once when the message enters timeout
        //                 (edge-triggered); resets when the message arrives
        //                 again. Only generated for messages with timeout_ms.

        std::function<void(DriveStatus)> on_drive_status;
        std::function<void()>            on_drive_status_timeout;
        // ... one pair per plc_to_pc message that defines timeout_ms
        //     messages without timeout_ms only get the on_* data handler

        // pc_to_plc messages have no RX or timeout handlers
        // (they are sent, not received)
    };

    // Socket created internally; filters derived from non-null handlers.
    CanInterface(std::string can_device, Handlers handlers);
    ~CanInterface();

    // Read up to max_frames from the socket, dispatch to registered handlers.
    // After draining frames, checks timeouts for messages that have a
    // non-null on_*_timeout handler. Always non-blocking — returns
    // immediately if no frames are available. Call from read() or a
    // thread loop — caller controls cadence.
    void process_frames(size_t max_frames = 5);

    // Block until at least one frame is available on the socket (or the
    // socket is closed). Use this to build a dedicated receive thread:
    //
    //   while (running_) {
    //       can.wait_readable();
    //       can.process_frames();
    //   }
    //
    // Internally calls poll() on the socket fd with no timeout.
    void wait_readable();

    // Send helpers — thin wrappers around build_* + socket send.
    // Propagates std::runtime_error on socket failure.
    void send(const MotorCommand &msg);
    void send(const PcState &msg);
    // ... one overload per pc_to_plc message

private:
    std::vector<can_filter> compute_filters() const;
    void check_timeouts(std::chrono::steady_clock::time_point now);

    Handlers handlers_;

    // Per-message timeout tracking — one entry per plc_to_pc message
    // that has a non-null on_*_timeout handler.
    struct MessageTimeoutState {
        std::chrono::milliseconds timeout;          // from YAML timeout_ms
        std::chrono::steady_clock::time_point last_received;
        bool timed_out = false;
    };
    // Generated as named members (e.g. drive_status_timeout_state_),
    // not a container — the set is fixed at compile time.

    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace project_can
```

**Key design points:**
- Each `plc_to_pc` message gets up to two handlers: `on_*` (data) and `on_*_timeout`. Both are independently optional. A message is added to the socket filter if *either* is non-null — so you can monitor timeouts without caring about the data, or consume data without timeout tracking.
- `send()` is overloaded on message struct type — one overload per pc_to_plc message. Propagates `std::runtime_error` on socket failure.
- Timeouts are edge-triggered and checked at the tail of every `process_frames()` call. When a message with a non-null `on_*_timeout` handler hasn't been received within its `timeout_ms`, the handler fires once. It resets when the message arrives again. The *response* to timeout (NaN, log, ignore) is the caller's responsibility since it varies per consumer.
- The socket is non-blocking. `process_frames` drains up to `max_frames` per call and returns immediately if no frames are available. This guarantees bounded execution time — it will never block waiting for frames to arrive.
- `wait_readable()` provides opt-in blocking for consumers that want a dedicated receive thread. It blocks on `poll()` until the socket has data, then returns so the caller can drain with `process_frames()`. This keeps the blocking/non-blocking concerns cleanly separated.

**Example usage (non-blocking poll, e.g. ros2_control hardware interface):**

```cpp
// on_configure:
can_ = std::make_unique<CanInterface>("can0", CanInterface::Handlers{
    .on_drive_status = [this](DriveStatus s) {
        actual_velocity_ = s.actual_velocity_rpm;
        motor_temp_      = s.motor_temp_degC;
    },
    .on_drive_status_timeout = [this]() {
        actual_velocity_ = std::numeric_limits<double>::quiet_NaN();
        motor_temp_      = std::numeric_limits<double>::quiet_NaN();
        RCLCPP_WARN(get_logger(), "drive_status timed out");
    },
});

// read():
can_->process_frames(5);

// write():
can_->send(MotorCommand{
    .target_velocity_rpm = cmd_velocity_,
    .torque_limit_Nm    = torque_limit_,
});
```

**Example usage (blocking receive thread, e.g. sensor publisher node):**

```cpp
// on_configure:
can_ = std::make_unique<CanInterface>("can0", CanInterface::Handlers{
    .on_inclinometer_imu = [this](InclinometerImu msg) {
        publish_imu(msg);
    },
});

// Dedicated receive thread — blocks until data arrives, then drains.
running_ = true;
receive_thread_ = std::thread([this]() {
    while (running_) {
        can_->wait_readable();
        can_->process_frames();
    }
});
```

---

## 5. Packing Report

The generator always produces a human-readable packing report (`packing_report.txt`)
alongside the generated code. This file is intended to be committed to the consuming
repo so that changes to message layout are visible in code review diffs.

### 5.1 Report format

```
can_commsgen packing report
Generated: 2026-03-25T14:00:00Z
Schema:    schema/control.yaml, schema/sensors.yaml

================================================================================
motor_command  (0x00000100, pc_to_plc, timeout 500ms)
  DLC: 4 bytes (32 bits used / 64 max)
--------------------------------------------------------------------------------
  Bit offset  Bits  Signed  Field               Type   Wire range          Physical range        Resolution
  0           16    yes     target_velocity      real   [-32000, 32000]     [-3200.0, 3200.0] rpm 0.1
  16          16    no      torque_limit         real   [0, 65535]          [0.0, 655.35] Nm      0.01
================================================================================

================================================================================
drive_status  (0x00000200, plc_to_pc)
  DLC: 6 bytes (46 bits used / 64 max)
--------------------------------------------------------------------------------
  Bit offset  Bits  Signed  Field               Type   Wire range          Physical range          Resolution
  0           16    yes     actual_velocity      real   [-32000, 32000]     [-3200.0, 3200.0] rpm   0.1
  16          12    yes     motor_temp           real   [-400, 2000]        [-40.0, 200.0] degC     0.1
  28          10    no      bus_voltage          real   [0, 1023]           [0.0, 102.3] V          0.1
  38          8     no      fault_code           uint8  [0, 255]            —                       —
================================================================================

================================================================================
pc_state  (0x00000300, pc_to_plc, timeout 1000ms)
  DLC: 1 bytes (2 bits used / 64 max)
--------------------------------------------------------------------------------
  Bit offset  Bits  Signed  Field               Type        Wire range   Physical range  Resolution
  0           2     no      drive_mode           DriveMode   [0, 3]      —               —
================================================================================
```

The report shows, for every message:
- CAN ID, direction, timeout (if set)
- Computed DLC and total bits used vs. 64-bit CAN maximum
- Per-field: bit offset, packed bit width, signedness, endpoint type, wire range,
  physical range with unit, and resolution

This makes it easy to spot when a schema change shifts bit offsets, changes DLC, or
alters wire ranges — all visible in a standard diff.

### 5.2 Error messages

When fields cannot be successfully packed into a message, the generator must produce
clear, actionable error messages that show what went wrong and how to fix it.

**Frame overflow:**

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

**Field-level inference issues:**

```
ERROR: Field 'pressure' in message 'sensor_data' (0x00000400):
  type: real, min: -100.0, max: 5000.0, resolution: 0.001
  Inferred wire range: [-100000, 5000000] → requires 23 bits (signed)

  This single field uses 23 of 64 available bits.
  Consider whether resolution: 0.001 is necessary, or widen to 0.01 (→ 20 bits)
  or 0.1 (→ 16 bits).
```

**Range vs endpoint type mismatch:**

```
ERROR: Field 'counter' in message 'heartbeat' (0x00000500):
  type: uint8, min: 0, max: 1024
  max value 1024 exceeds uint8 range [0, 255].

  Either widen the type to uint16, or reduce max to 255.
```

---

## 6. Generator Implementation

### 6.1 Language and dependencies

Python. Installable via [pixi](https://pixi.sh) as a git dependency — no PyPI release required.
Add to the consuming project's `pixi.toml`:

```toml
[pypi-dependencies]
can_commsgen = { git = "https://github.com/alistair-english/can_commsgen.git" }
```

Dependencies:
- `pyyaml` — schema parsing
- `jinja2` — code generation templates
- `click` — CLI

### 6.2 Directory layout

```
can_commsgen/             # repo root
  README.md
  templates/
    plc/
      enum.st.j2
      recv_fb.st.j2
      send_fb.st.j2
      gvl.st.j2
      main_input.st.j2
      bit_helpers.st.j2
    cpp/
      can_messages.hpp.j2
      can_interface.hpp.j2
      can_interface.cpp.j2
  can_commsgen/
    __init__.py
    schema.py             # schema loading, validation, normalisation, wire type inference
    plc.py                # PLC code generation
    cpp.py                # C++ code generation
    report.py             # packing report generation
  cli.py                  # CLI entrypoint (installed as `can_commsgen`)
  tests/
    test_schema.py
    test_plc_gen.py
    test_cpp_gen.py
```

Schema files live in the consuming project repo.

### 6.3 Schema validation

A JSON Schema definition is maintained for the YAML schema format. This provides
structural validation (required fields, types, allowed values) before the
processing pipeline runs. The JSON Schema file is shipped with the package and
used by `schema.py` during loading.

The schema is also available directly from GitHub for use with the VS Code YAML
extension. Add the following to the consuming project's `.vscode/settings.json`:

```json
{
  "yaml.schemas": {
    "https://raw.githubusercontent.com/greenforge-labs/can_commsgen/main/schema.json": "*.can.yaml"
  }
}
```

This provides autocomplete, validation, and hover docs for schema files in the
editor.

### 6.4 Schema processing pipeline

```
YAML file(s)
  → load & validate against JSON Schema (schema.py)
  → resolve enum types (look up wire type from enum definition)
  → infer wire representation:
      - real fields: compute wire range from min/max/resolution → derive bits + signedness
      - integer fields with min/max: derive minimum bits from range
      - integer fields without min/max: full width of endpoint type
      - bool: 1 bit
      - enum: minimum bits from enum's max value
  → bitpack: infer sequential bit offsets
  → compute DLC (total bits → ceil to bytes)
  → validate packing (frame overflow → error with field breakdown)
  → pass normalised model to PLC, C++, and report generators
```

Validation catches:
- `type: real` missing `min`, `max`, or `resolution`
- `resolution` used on non-real type
- `min`/`max` used on `bool` or enum type
- Integer `min`/`max` outside the range of the endpoint type
- Total frame bits > 64 (CAN max 8 bytes)
- Enum type referencing undeclared enum
- Duplicate message IDs (even across different directions)
- Missing required fields (`name`, `id`, `direction`, `type`)

### 6.5 CLI

```
can_commsgen \
  --schema path/to/schema.yaml \
  --out-plc path/to/plc/generated \
  --out-cpp path/to/cpp/generated \
  --out-report path/to/packing_report.txt
```

Multiple schema files can be passed; they are merged before generation:

```
can_commsgen \
  --schema schema/sensors.yaml \
  --schema schema/control.yaml \
  --out-plc ... \
  --out-cpp ... \
  --out-report ...
```

`--out-report` is optional but recommended. When provided, the generator writes the
packing report (see section 5) to the specified path. Commit this file alongside the
generated code so that packing changes are visible in diffs.

### 6.6 Naming conventions

| Schema | PLC ST | C++ |
|--------|--------|-----|
| `motor_command` | `MOTOR_COMMAND` (FB), `MOTOR_COMMAND_RECV` | `MotorCommand` (struct) |
| `drive_status` | `DRIVE_STATUS` (FB), `DRIVE_STATUS_SEND` | `DriveStatus` (struct) |
| `target_velocity` + `rpm` (field) | `targetVelocity_rpm` | `target_velocity_rpm` |
| `fault_code` (field, no unit) | `faultCode` | `fault_code` |
| `DriveMode` (enum) | `DriveMode` | `DriveMode` |

Variable names are derived from `name` + `unit`. PLC uses `camelCase_unit`, C++ uses
`snake_case_unit`. Fields without a `unit` use the name alone.

---

## 7. What Is Not Generated

- PLC send orchestration — the user decides when and how to call SEND FBs
- Timeout response logic — the C++ side fires `on_timeout` and the GVL provides
  `*WithinTimeout` booleans, but the fallback behaviour (zeroing values, defaulting
  to safe state, etc.) is the caller's responsibility
- Control logic (unit conversions, fallback behaviour, integrators, etc.)
- ROS node scaffolding (publishers, action servers, timers)
- Send rate limiting — the caller controls when and how often to call `send()`
- `SocketCAN` abstraction — `CanInterface` creates and owns its own raw Linux
  SocketCAN socket internally. There is no dependency on an external SocketCAN
  wrapper class.

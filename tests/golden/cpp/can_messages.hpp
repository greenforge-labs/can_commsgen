// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#pragma once
#include <cmath>
#include <cstdint>
#include <linux/can.h>
#include <optional>

namespace project_can {

// -- Enums --------------------------------------------------------------------

enum class DriveMode : uint8_t {
    IDLE = 0,
    VELOCITY = 1,
    POSITION = 2,
    TORQUE = 3,
};

// -- Message structs ----------------------------------------------------------

// motor_command (0x00000100, pc_to_plc, timeout 500ms)
struct MotorCommand {
    double target_velocity_rpm; // [-3200.0, 3200.0], res 0.1
    double torque_limit_Nm;     // [0.0, 655.35], res 0.01
};

// drive_status (0x00000200, plc_to_pc)
struct DriveStatus {
    double actual_velocity_rpm; // [-3200.0, 3200.0], res 0.1
    double motor_temp_degC;     // [-40.0, 200.0], res 0.1
    double bus_voltage_V;       // [0.0, 102.3], res 0.1
    uint8_t fault_code;
};

// pc_state (0x00000300, pc_to_plc, timeout 1000ms)
struct PcState {
    DriveMode drive_mode;
};

// -- Bit-level helpers --------------------------------------------------------

namespace detail {

inline int64_t extract_bits(const uint8_t data[8], uint16_t bit_offset, uint16_t bit_count, bool is_signed) {
    uint64_t raw = 0;
    for (uint16_t i = 0; i < bit_count; ++i) {
        uint16_t byte_idx = (bit_offset + i) / 8;
        uint16_t bit_idx = (bit_offset + i) % 8;
        if (data[byte_idx] & (1u << bit_idx))
            raw |= (uint64_t{1} << i);
    }
    if (is_signed && (raw & (uint64_t{1} << (bit_count - 1)))) {
        raw |= ~((uint64_t{1} << bit_count) - 1);
    }
    return static_cast<int64_t>(raw);
}

inline void insert_bits(uint8_t data[8], uint16_t bit_offset, uint16_t bit_count, int64_t value) {
    auto raw = static_cast<uint64_t>(value);
    for (uint16_t i = 0; i < bit_count; ++i) {
        uint16_t byte_idx = (bit_offset + i) / 8;
        uint16_t bit_idx = (bit_offset + i) % 8;
        if (raw & (uint64_t{1} << i))
            data[byte_idx] |= (1u << bit_idx);
        else
            data[byte_idx] &= ~(1u << bit_idx);
    }
}

} // namespace detail

// -- Parse functions (wire -> struct) -----------------------------------------

// motor_command (0x00000100, pc_to_plc, timeout 500ms)
inline std::optional<MotorCommand> parse_motor_command(const can_frame &frame) {
    if ((frame.can_id & CAN_EFF_MASK) != 0x00000100)
        return std::nullopt;
    if (frame.can_dlc != 4)
        return std::nullopt;

    MotorCommand msg;
    msg.target_velocity_rpm = detail::extract_bits(frame.data, 0, 16, true) * 0.1;
    msg.torque_limit_Nm = detail::extract_bits(frame.data, 16, 16, false) * 0.01;
    return msg;
}

// drive_status (0x00000200, plc_to_pc)
inline std::optional<DriveStatus> parse_drive_status(const can_frame &frame) {
    if ((frame.can_id & CAN_EFF_MASK) != 0x00000200)
        return std::nullopt;
    if (frame.can_dlc != 6)
        return std::nullopt;

    DriveStatus msg;
    msg.actual_velocity_rpm = detail::extract_bits(frame.data, 0, 16, true) * 0.1;
    msg.motor_temp_degC = detail::extract_bits(frame.data, 16, 12, true) * 0.1;
    msg.bus_voltage_V = detail::extract_bits(frame.data, 28, 10, false) * 0.1;
    msg.fault_code = static_cast<uint8_t>(detail::extract_bits(frame.data, 38, 8, false));
    return msg;
}

// pc_state (0x00000300, pc_to_plc, timeout 1000ms)
inline std::optional<PcState> parse_pc_state(const can_frame &frame) {
    if ((frame.can_id & CAN_EFF_MASK) != 0x00000300)
        return std::nullopt;
    if (frame.can_dlc != 1)
        return std::nullopt;

    PcState msg;
    msg.drive_mode = static_cast<DriveMode>(detail::extract_bits(frame.data, 0, 2, false));
    return msg;
}

// -- Build functions (struct -> wire) -----------------------------------------

// motor_command (0x00000100, pc_to_plc, timeout 500ms)
inline can_frame build_motor_command(const MotorCommand &msg) {
    can_frame frame{};
    frame.can_id = 0x00000100 | CAN_EFF_FLAG;
    frame.can_dlc = 4;

    detail::insert_bits(frame.data, 0, 16, static_cast<int64_t>(std::round(msg.target_velocity_rpm / 0.1)));
    detail::insert_bits(frame.data, 16, 16, static_cast<int64_t>(std::round(msg.torque_limit_Nm / 0.01)));
    return frame;
}

// drive_status (0x00000200, plc_to_pc)
inline can_frame build_drive_status(const DriveStatus &msg) {
    can_frame frame{};
    frame.can_id = 0x00000200 | CAN_EFF_FLAG;
    frame.can_dlc = 6;

    detail::insert_bits(frame.data, 0, 16, static_cast<int64_t>(std::round(msg.actual_velocity_rpm / 0.1)));
    detail::insert_bits(frame.data, 16, 12, static_cast<int64_t>(std::round(msg.motor_temp_degC / 0.1)));
    detail::insert_bits(frame.data, 28, 10, static_cast<int64_t>(std::round(msg.bus_voltage_V / 0.1)));
    detail::insert_bits(frame.data, 38, 8, static_cast<int64_t>(msg.fault_code));
    return frame;
}

// pc_state (0x00000300, pc_to_plc, timeout 1000ms)
inline can_frame build_pc_state(const PcState &msg) {
    can_frame frame{};
    frame.can_id = 0x00000300 | CAN_EFF_FLAG;
    frame.can_dlc = 1;

    detail::insert_bits(frame.data, 0, 2, static_cast<int64_t>(msg.drive_mode));
    return frame;
}

} // namespace project_can

// C++ roundtrip test for generated CAN messages.
// Verifies: build(values) -> parse(frame) -> values match within resolution.
//
// This test is compiled against the GENERATED can_messages.hpp (not the golden
// file). If it compiles and passes, the generated pack/unpack logic is correct.

#include "can_messages.hpp"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>

static int tests_run = 0;
static int tests_passed = 0;

#define ASSERT_NEAR(actual, expected, tol, label)                              \
    do {                                                                       \
        tests_run++;                                                           \
        double a_ = (actual), e_ = (expected), t_ = (tol);                    \
        if (std::abs(a_ - e_) > t_) {                                         \
            std::fprintf(stderr, "FAIL: %s: expected %.6f, got %.6f (tol %.6f)\n", \
                         label, e_, a_, t_);                                   \
            std::exit(1);                                                      \
        }                                                                      \
        tests_passed++;                                                        \
    } while (0)

#define ASSERT_EQ(actual, expected, label)                                     \
    do {                                                                       \
        tests_run++;                                                           \
        if ((actual) != (expected)) {                                          \
            std::fprintf(stderr, "FAIL: %s: expected %d, got %d\n",           \
                         label, (int)(expected), (int)(actual));               \
            std::exit(1);                                                      \
        }                                                                      \
        tests_passed++;                                                        \
    } while (0)

using namespace project_can;

// ---------------------------------------------------------------------------
// motor_command roundtrip
// ---------------------------------------------------------------------------
void test_motor_command_nominal() {
    MotorCommand tx{};
    tx.target_velocity_rpm = 1234.5;
    tx.torque_limit_Nm     = 123.45;

    auto frame = build_motor_command(tx);
    auto rx = parse_motor_command(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->target_velocity_rpm, 1234.5, 0.1,  "motor_cmd.target_velocity nominal");
    ASSERT_NEAR(rx->torque_limit_Nm,     123.45, 0.01, "motor_cmd.torque_limit nominal");
}

void test_motor_command_negative() {
    MotorCommand tx{};
    tx.target_velocity_rpm = -3200.0;
    tx.torque_limit_Nm     = 0.0;

    auto frame = build_motor_command(tx);
    auto rx = parse_motor_command(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->target_velocity_rpm, -3200.0, 0.1,  "motor_cmd.target_velocity min");
    ASSERT_NEAR(rx->torque_limit_Nm,     0.0,     0.01, "motor_cmd.torque_limit min");
}

void test_motor_command_max() {
    MotorCommand tx{};
    tx.target_velocity_rpm = 3200.0;
    tx.torque_limit_Nm     = 655.35;

    auto frame = build_motor_command(tx);
    auto rx = parse_motor_command(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->target_velocity_rpm, 3200.0,  0.1,  "motor_cmd.target_velocity max");
    ASSERT_NEAR(rx->torque_limit_Nm,     655.35,  0.01, "motor_cmd.torque_limit max");
}

void test_motor_command_zero() {
    MotorCommand tx{};
    tx.target_velocity_rpm = 0.0;
    tx.torque_limit_Nm     = 0.0;

    auto frame = build_motor_command(tx);
    auto rx = parse_motor_command(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->target_velocity_rpm, 0.0, 0.1,  "motor_cmd.target_velocity zero");
    ASSERT_NEAR(rx->torque_limit_Nm,     0.0, 0.01, "motor_cmd.torque_limit zero");
}

void test_motor_command_wrong_id() {
    auto frame = build_motor_command(MotorCommand{0.0, 0.0});
    frame.can_id = 0x00000999 | CAN_EFF_FLAG;  // wrong ID
    auto rx = parse_motor_command(frame);
    assert(!rx.has_value());
    tests_run++;
    tests_passed++;
}

// ---------------------------------------------------------------------------
// drive_status roundtrip
// ---------------------------------------------------------------------------
void test_drive_status_nominal() {
    DriveStatus tx{};
    tx.actual_velocity_rpm = -500.3;
    tx.motor_temp_degC     = 85.2;
    tx.bus_voltage_V       = 48.0;
    tx.fault_code          = 7;

    auto frame = build_drive_status(tx);
    auto rx = parse_drive_status(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->actual_velocity_rpm, -500.3, 0.1,  "drive_status.actual_velocity nominal");
    ASSERT_NEAR(rx->motor_temp_degC,     85.2,   0.1,  "drive_status.motor_temp nominal");
    ASSERT_NEAR(rx->bus_voltage_V,       48.0,   0.1,  "drive_status.bus_voltage nominal");
    ASSERT_EQ(rx->fault_code,            7,             "drive_status.fault_code nominal");
}

void test_drive_status_extremes() {
    DriveStatus tx{};
    tx.actual_velocity_rpm = -3200.0;
    tx.motor_temp_degC     = -40.0;
    tx.bus_voltage_V       = 0.0;
    tx.fault_code          = 0;

    auto frame = build_drive_status(tx);
    auto rx = parse_drive_status(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->actual_velocity_rpm, -3200.0, 0.1, "drive_status.actual_velocity min");
    ASSERT_NEAR(rx->motor_temp_degC,     -40.0,   0.1, "drive_status.motor_temp min");
    ASSERT_NEAR(rx->bus_voltage_V,       0.0,     0.1, "drive_status.bus_voltage min");
    ASSERT_EQ(rx->fault_code,            0,             "drive_status.fault_code min");
}

void test_drive_status_max() {
    DriveStatus tx{};
    tx.actual_velocity_rpm = 3200.0;
    tx.motor_temp_degC     = 200.0;
    tx.bus_voltage_V       = 102.3;
    tx.fault_code          = 255;

    auto frame = build_drive_status(tx);
    auto rx = parse_drive_status(frame);
    assert(rx.has_value());

    ASSERT_NEAR(rx->actual_velocity_rpm, 3200.0, 0.1, "drive_status.actual_velocity max");
    ASSERT_NEAR(rx->motor_temp_degC,     200.0,  0.1, "drive_status.motor_temp max");
    ASSERT_NEAR(rx->bus_voltage_V,       102.3,  0.1, "drive_status.bus_voltage max");
    ASSERT_EQ(rx->fault_code,            255,          "drive_status.fault_code max");
}

// ---------------------------------------------------------------------------
// pc_state roundtrip
// ---------------------------------------------------------------------------
void test_pc_state_all_modes() {
    DriveMode modes[] = {
        DriveMode::IDLE,
        DriveMode::VELOCITY,
        DriveMode::POSITION,
        DriveMode::TORQUE,
    };

    for (auto mode : modes) {
        PcState tx{};
        tx.drive_mode = mode;

        auto frame = build_pc_state(tx);
        auto rx = parse_pc_state(frame);
        assert(rx.has_value());

        ASSERT_EQ(static_cast<int>(rx->drive_mode), static_cast<int>(mode),
                  "pc_state.drive_mode");
    }
}

// ---------------------------------------------------------------------------
// DLC and CAN ID checks
// ---------------------------------------------------------------------------
void test_frame_metadata() {
    {
        auto f = build_motor_command(MotorCommand{0.0, 0.0});
        ASSERT_EQ(f.can_dlc, 4,  "motor_command DLC");
        ASSERT_EQ(f.can_id & CAN_EFF_MASK, 0x00000100, "motor_command CAN ID");
        assert(f.can_id & CAN_EFF_FLAG);
        tests_run++; tests_passed++;
    }
    {
        auto f = build_drive_status(DriveStatus{0.0, 0.0, 0.0, 0});
        ASSERT_EQ(f.can_dlc, 6,  "drive_status DLC");
        ASSERT_EQ(f.can_id & CAN_EFF_MASK, 0x00000200, "drive_status CAN ID");
        assert(f.can_id & CAN_EFF_FLAG);
        tests_run++; tests_passed++;
    }
    {
        auto f = build_pc_state(PcState{DriveMode::IDLE});
        ASSERT_EQ(f.can_dlc, 1,  "pc_state DLC");
        ASSERT_EQ(f.can_id & CAN_EFF_MASK, 0x00000300, "pc_state CAN ID");
        assert(f.can_id & CAN_EFF_FLAG);
        tests_run++; tests_passed++;
    }
}

// ---------------------------------------------------------------------------
int main() {
    test_motor_command_nominal();
    test_motor_command_negative();
    test_motor_command_max();
    test_motor_command_zero();
    test_motor_command_wrong_id();

    test_drive_status_nominal();
    test_drive_status_extremes();
    test_drive_status_max();

    test_pc_state_all_modes();

    test_frame_metadata();

    std::printf("OK: %d/%d tests passed\n", tests_passed, tests_run);
    return 0;
}

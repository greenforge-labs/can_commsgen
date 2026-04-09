// Runtime tests for the generated CanInterface class.
// Exercises: construction, send, process_frames dispatch, filter installation,
// and destructor cleanup — all via injectable stub syscalls (stub_state.h).

#include "can_interface.hpp"
#include "stub_state.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <utility>

static int tests_run = 0;
static int tests_passed = 0;

#define PASS(label)                                                                                                    \
    do {                                                                                                               \
        tests_run++;                                                                                                   \
        tests_passed++;                                                                                                \
        std::printf("  pass: %s\n", label);                                                                            \
    } while (0)

#define FAIL(label, msg)                                                                                               \
    do {                                                                                                               \
        tests_run++;                                                                                                   \
        std::fprintf(stderr, "FAIL: %s: %s\n", label, msg);                                                            \
        std::exit(1);                                                                                                  \
    } while (0)

#define ASSERT_TRUE(cond, label)                                                                                       \
    do {                                                                                                               \
        if (!(cond))                                                                                                   \
            FAIL(label, "expected true");                                                                              \
        PASS(label);                                                                                                   \
    } while (0)

#define ASSERT_EQ(actual, expected, label)                                                                             \
    do {                                                                                                               \
        if ((actual) != (expected)) {                                                                                  \
            std::fprintf(stderr, "FAIL: %s: expected %d, got %d\n", label, (int)(expected), (int)(actual));            \
            tests_run++;                                                                                               \
            std::exit(1);                                                                                              \
        }                                                                                                              \
        PASS(label);                                                                                                   \
    } while (0)

#define ASSERT_NEAR(actual, expected, tol, label)                                                                      \
    do {                                                                                                               \
        double a_ = (actual), e_ = (expected), t_ = (tol);                                                             \
        if (std::abs(a_ - e_) > t_) {                                                                                  \
            std::fprintf(stderr, "FAIL: %s: expected %.6f, got %.6f\n", label, e_, a_);                                \
            tests_run++;                                                                                               \
            std::exit(1);                                                                                              \
        }                                                                                                              \
        PASS(label);                                                                                                   \
    } while (0)

using namespace plc_can;

// Helper: default handlers with no callbacks set.
static CanInterface::Handlers empty_handlers() { return {}; }

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------
void test_construction_success() {
    std::printf("test_construction_success\n");
    stub().reset();

    auto iface = CanInterface("vcan0", empty_handlers());
    PASS("construction does not throw");
}

void test_construction_socket_failure() {
    std::printf("test_construction_socket_failure\n");
    stub().reset();
    stub().socket_fail = true;

    bool threw = false;
    try {
        CanInterface("vcan0", empty_handlers());
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "socket failure throws runtime_error");
}

void test_construction_ioctl_failure() {
    std::printf("test_construction_ioctl_failure\n");
    stub().reset();
    stub().ioctl_fail = true;

    bool threw = false;
    try {
        CanInterface("vcan0", empty_handlers());
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "ioctl failure throws runtime_error");
}

void test_construction_bind_failure() {
    std::printf("test_construction_bind_failure\n");
    stub().reset();
    stub().bind_fail = true;

    bool threw = false;
    try {
        CanInterface("vcan0", empty_handlers());
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "bind failure throws runtime_error");
}

void test_construction_setsockopt_failure() {
    std::printf("test_construction_setsockopt_failure\n");
    stub().reset();
    stub().setsockopt_fail = true;

    // Need a handler set so that filters are non-empty and setsockopt is called
    CanInterface::Handlers h{};
    h.on_drive_status = [](DriveStatus) {};

    bool threw = false;
    try {
        CanInterface("vcan0", h);
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "setsockopt failure throws runtime_error");
}

// ---------------------------------------------------------------------------
// send()
// ---------------------------------------------------------------------------
void test_send_motor_command() {
    std::printf("test_send_motor_command\n");
    stub().reset();

    auto iface = CanInterface("vcan0", empty_handlers());
    stub().tx_log.clear();

    MotorCommand cmd{};
    cmd.target_velocity_rpm = 1234.5;
    cmd.torque_limit_Nm = 56.78;
    iface.send(cmd);

    ASSERT_EQ(stub().tx_log.size(), 1, "one frame sent");

    auto &f = stub().tx_log[0];
    ASSERT_EQ(f.can_id & CAN_EFF_MASK, 0x00000100, "motor_command CAN ID");
    ASSERT_TRUE(f.can_id & CAN_EFF_FLAG, "EFF flag set");
    ASSERT_EQ(f.can_dlc, 4, "motor_command DLC");

    // Roundtrip through parse to verify payload
    auto parsed = parse_motor_command(f);
    ASSERT_TRUE(parsed.has_value(), "parse succeeds");
    ASSERT_NEAR(parsed->target_velocity_rpm, 1234.5, 0.1, "velocity roundtrip");
    ASSERT_NEAR(parsed->torque_limit_Nm, 56.78, 0.01, "torque roundtrip");
}

void test_send_pc_state() {
    std::printf("test_send_pc_state\n");
    stub().reset();

    auto iface = CanInterface("vcan0", empty_handlers());
    stub().tx_log.clear();

    PcState st{DriveMode::TORQUE};
    iface.send(st);

    ASSERT_EQ(stub().tx_log.size(), 1, "one frame sent");

    auto &f = stub().tx_log[0];
    ASSERT_EQ(f.can_id & CAN_EFF_MASK, 0x00000300, "pc_state CAN ID");
    ASSERT_EQ(f.can_dlc, 1, "pc_state DLC");

    auto parsed = parse_pc_state(f);
    ASSERT_TRUE(parsed.has_value(), "parse succeeds");
    ASSERT_EQ(static_cast<int>(parsed->drive_mode), static_cast<int>(DriveMode::TORQUE), "drive_mode roundtrip");
}

// ---------------------------------------------------------------------------
// process_frames() dispatch
// ---------------------------------------------------------------------------
void test_process_frames_dispatches_drive_status() {
    std::printf("test_process_frames_dispatches_drive_status\n");
    stub().reset();

    bool called = false;
    DriveStatus received{};

    CanInterface::Handlers h{};
    h.on_drive_status = [&](DriveStatus ds) {
        called = true;
        received = ds;
    };

    auto iface = CanInterface("vcan0", h);

    // Enqueue a valid drive_status frame
    DriveStatus tx{};
    tx.actual_velocity_rpm = -500.3;
    tx.motor_temp_degC = 85.2;
    tx.bus_voltage_V = 48.0;
    tx.fault_code = 7;
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;

    iface.process_frames();

    ASSERT_TRUE(called, "handler was called");
    ASSERT_NEAR(received.actual_velocity_rpm, -500.3, 0.1, "velocity dispatched");
    ASSERT_NEAR(received.motor_temp_degC, 85.2, 0.1, "temp dispatched");
    ASSERT_NEAR(received.bus_voltage_V, 48.0, 0.1, "voltage dispatched");
    ASSERT_EQ(received.fault_code, 7, "fault_code dispatched");
}

void test_process_frames_ignores_unknown_id() {
    std::printf("test_process_frames_ignores_unknown_id\n");
    stub().reset();

    bool called = false;
    CanInterface::Handlers h{};
    h.on_drive_status = [&](DriveStatus) { called = true; };

    auto iface = CanInterface("vcan0", h);

    // Enqueue a frame with an ID not in the schema
    can_frame bogus{};
    bogus.can_id = 0x00000999 | CAN_EFF_FLAG;
    bogus.can_dlc = 4;
    stub().rx_queue.push_back(bogus);
    stub().rx_pos = 0;

    iface.process_frames();

    ASSERT_TRUE(!called, "handler NOT called for unknown ID");
}

void test_process_frames_respects_max_frames() {
    std::printf("test_process_frames_respects_max_frames\n");
    stub().reset();

    int call_count = 0;
    CanInterface::Handlers h{};
    h.on_drive_status = [&](DriveStatus) { ++call_count; };

    auto iface = CanInterface("vcan0", h);

    // Enqueue 3 valid drive_status frames
    DriveStatus tx{0.0, 0.0, 0.0, 0};
    for (int i = 0; i < 3; ++i)
        stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;

    iface.process_frames(/*max_frames=*/1);

    ASSERT_EQ(call_count, 1, "only 1 frame processed when max_frames=1");
}

void test_process_frames_no_handler_set() {
    std::printf("test_process_frames_no_handler_set\n");
    stub().reset();

    // No handlers set — should silently ignore the frame
    auto iface = CanInterface("vcan0", empty_handlers());

    DriveStatus tx{0.0, 0.0, 0.0, 0};
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;

    iface.process_frames(); // should not crash
    PASS("no crash with unset handler");
}

void test_process_frames_eintr_retries() {
    std::printf("test_process_frames_eintr_retries\n");
    stub().reset();

    int call_count = 0;
    CanInterface::Handlers h{};
    h.on_drive_status = [&](DriveStatus) { ++call_count; };

    auto iface = CanInterface("vcan0", h);

    // Enqueue 2 frames, but inject EINTR before the first
    DriveStatus tx{0.0, 0.0, 0.0, 0};
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;
    stub().read_errno_at = 0;
    stub().read_errno_val = EINTR;

    iface.process_frames(/*max_frames=*/5);

    ASSERT_EQ(call_count, 2, "both frames processed despite EINTR");
}

void test_process_frames_real_error_throws() {
    std::printf("test_process_frames_real_error_throws\n");
    stub().reset();

    CanInterface::Handlers h{};
    h.on_drive_status = [](DriveStatus) {};

    auto iface = CanInterface("vcan0", h);

    // Inject EIO (a real error, not EAGAIN/EINTR)
    DriveStatus tx{0.0, 0.0, 0.0, 0};
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;
    stub().read_errno_at = 0;
    stub().read_errno_val = 5; // EIO

    bool threw = false;
    try {
        iface.process_frames();
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "real read error throws runtime_error");
}

void test_process_frames_incomplete_frame_throws() {
    std::printf("test_process_frames_incomplete_frame_throws\n");
    stub().reset();

    auto iface = CanInterface("vcan0", empty_handlers());

    DriveStatus tx{0.0, 0.0, 0.0, 0};
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;
    stub().read_short = true;

    bool threw = false;
    try {
        iface.process_frames();
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "incomplete frame throws runtime_error");
}

void test_send_failure_throws() {
    std::printf("test_send_failure_throws\n");
    stub().reset();

    auto iface = CanInterface("vcan0", empty_handlers());
    stub().write_fail = true;

    bool threw = false;
    try {
        MotorCommand cmd{};
        iface.send(cmd);
    } catch (const std::runtime_error &) {
        threw = true;
    }
    ASSERT_TRUE(threw, "send failure throws runtime_error");
}

// ---------------------------------------------------------------------------
// Filter installation
// ---------------------------------------------------------------------------
void test_filters_installed_with_handler() {
    std::printf("test_filters_installed_with_handler\n");
    stub().reset();

    CanInterface::Handlers h{};
    h.on_drive_status = [](DriveStatus) {};

    auto iface = CanInterface("vcan0", h);

    ASSERT_EQ(stub().installed_filters.size(), 1, "one filter installed");
    ASSERT_EQ(stub().installed_filters[0].can_id, 0x00000200 | CAN_EFF_FLAG, "filter matches drive_status ID");
}

void test_no_filters_without_handlers() {
    std::printf("test_no_filters_without_handlers\n");
    stub().reset();

    auto iface = CanInterface("vcan0", empty_handlers());

    ASSERT_EQ(stub().installed_filters.size(), 0, "no filters without handlers");
}

// ---------------------------------------------------------------------------
// Move semantics
// ---------------------------------------------------------------------------
void test_move_constructor() {
    std::printf("test_move_constructor\n");
    stub().reset();

    int call_count = 0;
    CanInterface::Handlers h{};
    h.on_drive_status = [&](DriveStatus) { ++call_count; };

    auto original = CanInterface("vcan0", h);
    auto moved = std::move(original);

    // moved instance should work — send and receive
    DriveStatus tx{0.0, 0.0, 0.0, 0};
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;
    moved.process_frames();

    ASSERT_EQ(call_count, 1, "moved instance dispatches frames");
}

void test_move_assignment() {
    std::printf("test_move_assignment\n");
    stub().reset();

    auto first = CanInterface("vcan0", empty_handlers());
    stub().closed_fds.clear();

    int call_count = 0;
    CanInterface::Handlers h{};
    h.on_drive_status = [&](DriveStatus) { ++call_count; };

    auto second = CanInterface("vcan0", h);

    // Move-assign second into first — first's old fd should be closed
    first = std::move(second);

    ASSERT_EQ(stub().closed_fds.size(), 1, "old fd closed on move-assign");

    DriveStatus tx{0.0, 0.0, 0.0, 0};
    stub().rx_queue.push_back(build_drive_status(tx));
    stub().rx_pos = 0;
    first.process_frames();

    ASSERT_EQ(call_count, 1, "move-assigned instance dispatches frames");
}

// ---------------------------------------------------------------------------
// Destructor
// ---------------------------------------------------------------------------
void test_destructor_closes_socket() {
    std::printf("test_destructor_closes_socket\n");
    stub().reset();

    {
        auto iface = CanInterface("vcan0", empty_handlers());
    } // destructor runs here

    ASSERT_TRUE(stub().was_closed, "socket closed on destruction");
    ASSERT_EQ(stub().closed_fd, 42, "correct fd closed");
}

// ---------------------------------------------------------------------------
int main() {
    test_construction_success();
    test_construction_socket_failure();
    test_construction_ioctl_failure();
    test_construction_bind_failure();
    test_construction_setsockopt_failure();

    test_send_motor_command();
    test_send_pc_state();
    test_send_failure_throws();

    test_process_frames_dispatches_drive_status();
    test_process_frames_ignores_unknown_id();
    test_process_frames_respects_max_frames();
    test_process_frames_no_handler_set();
    test_process_frames_eintr_retries();
    test_process_frames_real_error_throws();
    test_process_frames_incomplete_frame_throws();

    test_filters_installed_with_handler();
    test_no_filters_without_handlers();

    test_move_constructor();
    test_move_assignment();

    test_destructor_closes_socket();

    std::printf("\nOK: %d/%d can_interface tests passed\n", tests_passed, tests_run);
    return 0;
}

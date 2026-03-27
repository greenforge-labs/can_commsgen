// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#pragma once
#include <chrono>
#include <functional>
#include <string>
#include <vector>
#include <linux/can.h>
#include "can_messages.hpp"

namespace project_can {

class CanInterface {
public:
    struct Handlers {
        // drive_status (0x00000200, plc_to_pc)
        std::function<void(DriveStatus)> on_drive_status;
    };

    CanInterface(std::string can_device, Handlers handlers);
    ~CanInterface();

    CanInterface(const CanInterface &) = delete;
    CanInterface &operator=(const CanInterface &) = delete;

    CanInterface(CanInterface &&other) noexcept;
    CanInterface &operator=(CanInterface &&other) noexcept;

    void process_frames(size_t max_frames = 5);
    void wait_readable();

    // pc_to_plc send overloads
    void send(const MotorCommand &msg);
    void send(const PcState &msg);

private:
    std::vector<can_filter> compute_filters() const;
    void check_timeouts(std::chrono::steady_clock::time_point now);

    int socket_fd_ = -1;
    Handlers handlers_;
};

} // namespace project_can

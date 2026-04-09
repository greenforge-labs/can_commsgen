// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#pragma once
#include "can_messages.hpp"
#include <chrono>
#include <functional>
#include <linux/can.h>
#include <string>
#include <vector>

namespace plc_can {

class CanInterface {
  public:
    struct Handlers {
        // drive_status (0x00000200, plc_to_pc, timeout 200ms)
        std::function<void(DriveStatus)> on_drive_status;
        std::function<void()> on_drive_status_timeout;
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

    struct DriveStatusTimeoutState {
        std::chrono::milliseconds timeout{200};
        std::chrono::steady_clock::time_point last_received;
    };
    DriveStatusTimeoutState drive_status_timeout_state_;

    int socket_fd_ = -1;
    Handlers handlers_;
};

} // namespace plc_can

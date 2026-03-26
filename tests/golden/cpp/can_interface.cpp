// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#include <poll.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <unistd.h>
#include <cstring>
#include <stdexcept>
#include "can_interface.hpp"

namespace project_can {

struct CanInterface::Impl {
    int socket_fd = -1;
};

CanInterface::CanInterface(std::string can_device, Handlers handlers)
    : impl_(std::make_unique<Impl>()), handlers_(std::move(handlers)) {
    impl_->socket_fd = socket(PF_CAN, SOCK_RAW | SOCK_NONBLOCK, CAN_RAW);
    if (impl_->socket_fd < 0) {
        throw std::runtime_error("Failed to create CAN socket");
    }

    struct ifreq ifr{};
    std::strncpy(ifr.ifr_name, can_device.c_str(), IFNAMSIZ - 1);
    if (ioctl(impl_->socket_fd, SIOCGIFINDEX, &ifr) < 0) {
        close(impl_->socket_fd);
        throw std::runtime_error("Failed to get interface index for " + can_device);
    }

    struct sockaddr_can addr{};
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    auto filters = compute_filters();
    if (!filters.empty()) {
        setsockopt(impl_->socket_fd, SOL_CAN_RAW, CAN_RAW_FILTER,
                   filters.data(), filters.size() * sizeof(can_filter));
    }

    if (bind(impl_->socket_fd, reinterpret_cast<struct sockaddr *>(&addr),
             sizeof(addr)) < 0) {
        close(impl_->socket_fd);
        throw std::runtime_error("Failed to bind CAN socket");
    }
}

CanInterface::~CanInterface() {
    if (impl_ && impl_->socket_fd >= 0) {
        close(impl_->socket_fd);
    }
}

void CanInterface::process_frames(size_t max_frames) {
    for (size_t i = 0; i < max_frames; ++i) {
        can_frame frame{};
        auto n = read(impl_->socket_fd, &frame, sizeof(frame));
        if (n != sizeof(frame)) break;

        uint32_t id = frame.can_id & CAN_EFF_MASK;
        switch (id) {
            case 0x00000200:
                if (handlers_.on_drive_status) {
                    auto parsed = parse_drive_status(frame);
                    if (parsed) handlers_.on_drive_status(*parsed);
                }
                break;
        }
    }

    auto now = std::chrono::steady_clock::now();
    check_timeouts(now);
}

void CanInterface::wait_readable() {
    struct pollfd pfd{};
    pfd.fd = impl_->socket_fd;
    pfd.events = POLLIN;
    poll(&pfd, 1, -1);
}

void CanInterface::send(const MotorCommand &msg) {
    auto frame = build_motor_command(msg);
    if (write(impl_->socket_fd, &frame, sizeof(frame)) != sizeof(frame)) {
        throw std::runtime_error("Failed to send motor_command");
    }
}

void CanInterface::send(const PcState &msg) {
    auto frame = build_pc_state(msg);
    if (write(impl_->socket_fd, &frame, sizeof(frame)) != sizeof(frame)) {
        throw std::runtime_error("Failed to send pc_state");
    }
}

std::vector<can_filter> CanInterface::compute_filters() const {
    std::vector<can_filter> filters;

    // drive_status (0x00000200, plc_to_pc)
    if (handlers_.on_drive_status) {
        filters.push_back({0x00000200 | CAN_EFF_FLAG, CAN_EFF_FLAG | CAN_EFF_MASK});
    }

    return filters;
}

void CanInterface::check_timeouts(std::chrono::steady_clock::time_point /*now*/) {
    // No plc_to_pc messages with timeout_ms in this schema.
}

} // namespace project_can

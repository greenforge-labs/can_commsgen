// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.
#include "can_interface.hpp"
#include <cstring>
#include <errno.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <poll.h>
#include <stdexcept>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

namespace plc_can {

CanInterface::CanInterface(std::string can_device, Handlers handlers) : handlers_(std::move(handlers)) {
    socket_fd_ = socket(PF_CAN, SOCK_RAW | SOCK_NONBLOCK, CAN_RAW);
    if (socket_fd_ < 0) {
        throw std::runtime_error("Failed to create CAN socket: " + std::string(strerror(errno)));
    }

    struct ifreq ifr;
    std::strncpy(ifr.ifr_name, can_device.c_str(), IFNAMSIZ - 1);
    ifr.ifr_name[IFNAMSIZ - 1] = '\0';

    if (ioctl(socket_fd_, SIOCGIFINDEX, &ifr) < 0) {
        close(socket_fd_);
        throw std::runtime_error(
            "Failed to get interface index for " + can_device + ": " + std::string(strerror(errno))
        );
    }

    struct sockaddr_can addr{};
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(socket_fd_, reinterpret_cast<struct sockaddr *>(&addr), sizeof(addr)) < 0) {
        close(socket_fd_);
        throw std::runtime_error("Failed to bind CAN socket: " + std::string(strerror(errno)));
    }

    auto filters = compute_filters();
    if (!filters.empty()) {
        if (setsockopt(socket_fd_, SOL_CAN_RAW, CAN_RAW_FILTER, filters.data(), filters.size() * sizeof(can_filter)) <
            0) {
            close(socket_fd_);
            throw std::runtime_error("Failed to set CAN filters: " + std::string(strerror(errno)));
        }
    }
}

CanInterface::~CanInterface() {
    if (socket_fd_ >= 0) {
        close(socket_fd_);
    }
}

CanInterface::CanInterface(CanInterface &&other) noexcept
    : socket_fd_(other.socket_fd_), handlers_(std::move(other.handlers_)) {
    other.socket_fd_ = -1;
}

CanInterface &CanInterface::operator=(CanInterface &&other) noexcept {
    if (this != &other) {
        if (socket_fd_ >= 0) {
            close(socket_fd_);
        }
        socket_fd_ = other.socket_fd_;
        handlers_ = std::move(other.handlers_);
        other.socket_fd_ = -1;
    }
    return *this;
}

void CanInterface::process_frames(size_t max_frames) {
    for (size_t i = 0; i < max_frames; ++i) {
        can_frame frame{};
        auto n = read(socket_fd_, &frame, sizeof(frame));
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                break;
            }
            if (errno == EINTR) {
                continue;
            }
            throw std::runtime_error("Failed to read CAN frame: " + std::string(strerror(errno)));
        }
        if (n != static_cast<ssize_t>(sizeof(frame))) {
            throw std::runtime_error("Incomplete CAN frame received");
        }

        uint32_t id = frame.can_id & CAN_EFF_MASK;
        switch (id) {
        case 0x00000200:
            if (handlers_.on_drive_status) {
                auto parsed = parse_drive_status(frame);
                if (parsed)
                    handlers_.on_drive_status(*parsed);
            }
            break;
        }
    }

    auto now = std::chrono::steady_clock::now();
    check_timeouts(now);
}

void CanInterface::wait_readable() {
    struct pollfd pfd{};
    pfd.fd = socket_fd_;
    pfd.events = POLLIN;
    poll(&pfd, 1, -1);
}

void CanInterface::send(const MotorCommand &msg) {
    auto frame = build_motor_command(msg);
    if (write(socket_fd_, &frame, sizeof(frame)) != sizeof(frame)) {
        throw std::runtime_error("Failed to send motor_command: " + std::string(strerror(errno)));
    }
}

void CanInterface::send(const PcState &msg) {
    auto frame = build_pc_state(msg);
    if (write(socket_fd_, &frame, sizeof(frame)) != sizeof(frame)) {
        throw std::runtime_error("Failed to send pc_state: " + std::string(strerror(errno)));
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

} // namespace plc_can

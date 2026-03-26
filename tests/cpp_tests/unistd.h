// Minimal unistd.h stub with functional behavior for runtime testing.
#pragma once
#include <cstddef>
#include <cstring>
#include <stub_state.h>

inline long read(int /*fd*/, void *buf, size_t count) {
    auto &s = stub();
    if (s.rx_pos >= s.rx_queue.size()) return -1;
    if (count < sizeof(can_frame)) return -1;
    std::memcpy(buf, &s.rx_queue[s.rx_pos], sizeof(can_frame));
    ++s.rx_pos;
    return static_cast<long>(sizeof(can_frame));
}

inline long write(int /*fd*/, const void *buf, size_t count) {
    if (count == sizeof(can_frame)) {
        can_frame f{};
        std::memcpy(&f, buf, sizeof(f));
        stub().tx_log.push_back(f);
    }
    return static_cast<long>(count);
}

inline int close(int fd) {
    auto &s = stub();
    s.was_closed = true;
    s.closed_fd = fd;
    return 0;
}

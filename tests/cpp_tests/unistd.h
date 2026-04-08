// Minimal unistd.h stub with functional behavior for runtime testing.
#pragma once
#include <cstddef>
#include <cstring>
#include <errno.h>
#include <stub_state.h>

int errno = 0;

inline long read(int /*fd*/, void *buf, size_t count) {
    auto &s = stub();
    if (s.read_errno_at >= 0 && static_cast<int>(s.rx_pos) == s.read_errno_at) {
        errno = s.read_errno_val;
        s.read_errno_at = -1; // fire once
        return -1;
    }
    if (s.rx_pos >= s.rx_queue.size()) {
        errno = EAGAIN;
        return -1;
    }
    if (s.read_short) {
        s.read_short = false;
        return 4; // incomplete frame
    }
    if (count < sizeof(can_frame)) {
        errno = EAGAIN;
        return -1;
    }
    std::memcpy(buf, &s.rx_queue[s.rx_pos], sizeof(can_frame));
    ++s.rx_pos;
    return static_cast<long>(sizeof(can_frame));
}

inline long write(int /*fd*/, const void *buf, size_t count) {
    if (stub().write_fail)
        return -1;
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
    s.closed_fds.push_back(fd);
    return 0;
}

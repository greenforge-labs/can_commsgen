// Minimal poll.h stub for compile-only testing.
#pragma once

#define POLLIN 0x001

struct pollfd {
    int   fd;
    short events;
    short revents;
};

inline int poll(struct pollfd * /*fds*/, unsigned long /*nfds*/, int /*timeout*/) {
    return 0;
}

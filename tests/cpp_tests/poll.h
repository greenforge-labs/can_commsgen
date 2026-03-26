// Minimal poll.h stub with functional behavior for runtime testing.
#pragma once
#include <stub_state.h>

#define POLLIN 0x001

struct pollfd {
    int   fd;
    short events;
    short revents;
};

inline int poll(struct pollfd *fds, unsigned long nfds, int /*timeout*/) {
    if (nfds > 0 && !stub().rx_queue.empty()) {
        fds[0].revents = POLLIN;
    }
    return 1;
}

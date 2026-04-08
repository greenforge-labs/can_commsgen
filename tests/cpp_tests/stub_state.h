// Global test state for functional system-call stubs.
// Include this from stub headers so they can simulate real CAN socket behavior.
#pragma once

#include "linux/can.h"
#include <cstring>
#include <vector>

struct StubState {
    // --- construction control ---
    int next_fd = 42;
    bool socket_fail = false;
    bool ioctl_fail = false;
    bool bind_fail = false;
    bool setsockopt_fail = false;

    // --- read(): frames the test wants process_frames() to see ---
    std::vector<can_frame> rx_queue;
    size_t rx_pos = 0;
    int read_errno_at = -1;  // inject errno at this rx_pos index
    int read_errno_val = 0;  // errno value to inject (e.g. EINTR, EIO)
    bool read_short = false; // return incomplete frame

    // --- write(): frames captured from send() calls ---
    std::vector<can_frame> tx_log;
    bool write_fail = false;

    // --- setsockopt(): filters installed during construction ---
    std::vector<can_filter> installed_filters;

    // --- close() tracking ---
    bool was_closed = false;
    int closed_fd = -1;
    std::vector<int> closed_fds;

    void reset() { *this = StubState{}; }
};

inline StubState &stub() {
    static StubState s;
    return s;
}

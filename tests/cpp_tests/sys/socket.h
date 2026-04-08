// Minimal sys/socket.h stub with functional behavior for runtime testing.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <stub_state.h>

struct sockaddr {
    uint16_t sa_family;
    char sa_data[14];
};

inline int socket(int /*domain*/, int /*type*/, int /*protocol*/) { return stub().socket_fail ? -1 : stub().next_fd; }

inline int bind(int /*fd*/, const struct sockaddr * /*addr*/, unsigned int /*len*/) {
    return stub().bind_fail ? -1 : 0;
}

inline int setsockopt(int /*fd*/, int /*level*/, int /*optname*/, const void *optval, unsigned int optlen) {
    if (stub().setsockopt_fail)
        return -1;
    if (optval && optlen > 0) {
        size_t count = optlen / sizeof(can_filter);
        auto *filters = static_cast<const can_filter *>(optval);
        stub().installed_filters.assign(filters, filters + count);
    }
    return 0;
}

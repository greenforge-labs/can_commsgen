// Minimal sys/socket.h stub for compile-only testing.
#pragma once
#include <cstddef>
#include <cstdint>

struct sockaddr {
    uint16_t sa_family;
    char     sa_data[14];
};

inline int socket(int /*domain*/, int /*type*/, int /*protocol*/) { return -1; }
inline int bind(int /*fd*/, const struct sockaddr * /*addr*/, unsigned int /*len*/) { return -1; }
inline int setsockopt(int /*fd*/, int /*level*/, int /*optname*/,
                      const void * /*optval*/, unsigned int /*optlen*/) { return -1; }

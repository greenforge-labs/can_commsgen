// Minimal sys/ioctl.h stub with functional behavior for runtime testing.
#pragma once
#include <cstdarg>
#include <net/if.h>
#include <stub_state.h>

#define SIOCGIFINDEX 0x8933

inline int ioctl(int /*fd*/, unsigned long req, ...) {
    if (stub().ioctl_fail)
        return -1;

    va_list args;
    va_start(args, req);
    struct ifreq *ifr = va_arg(args, struct ifreq *);
    va_end(args);

    ifr->ifr_ifindex = 1;
    return 0;
}

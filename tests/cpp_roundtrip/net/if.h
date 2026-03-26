// Minimal net/if.h stub for compile-only testing.
#pragma once

#define IFNAMSIZ 16

struct ifreq {
    char ifr_name[IFNAMSIZ];
    int  ifr_ifindex;
};

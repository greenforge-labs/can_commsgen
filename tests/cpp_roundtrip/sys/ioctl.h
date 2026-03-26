// Minimal sys/ioctl.h stub for compile-only testing.
#pragma once

#define SIOCGIFINDEX 0x8933

inline int ioctl(int /*fd*/, unsigned long /*request*/, ...) { return -1; }

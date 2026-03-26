// Minimal unistd.h stub for compile-only testing.
#pragma once
#include <cstddef>

inline long read(int /*fd*/, void * /*buf*/, size_t /*count*/) { return -1; }
inline long write(int /*fd*/, const void * /*buf*/, size_t /*count*/) { return -1; }
inline int close(int /*fd*/) { return -1; }

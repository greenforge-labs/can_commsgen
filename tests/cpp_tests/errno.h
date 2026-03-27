// Minimal errno.h stub for runtime testing.
#pragma once

#define EAGAIN 11
#define EWOULDBLOCK EAGAIN
#define EINTR 4
#define ERANGE 34

extern int errno;

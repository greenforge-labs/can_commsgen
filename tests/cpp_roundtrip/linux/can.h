// Minimal linux/can.h stub for portable roundtrip testing.
// Only defines the subset used by can_messages.hpp.
#pragma once
#include <cstdint>

#define CAN_EFF_FLAG 0x80000000U
#define CAN_EFF_MASK 0x1FFFFFFFU

struct can_frame {
    uint32_t can_id;
    uint8_t  can_dlc;
    uint8_t  __pad;
    uint8_t  __res0;
    uint8_t  __res1;
    uint8_t  data[8];
};

// Minimal linux/can.h stub for portable roundtrip testing.
// Defines the subset used by can_messages.hpp and can_interface.hpp/cpp.
#pragma once
#include <cstdint>

#define CAN_EFF_FLAG 0x80000000U
#define CAN_EFF_MASK 0x1FFFFFFFU

#define PF_CAN 29
#define AF_CAN PF_CAN
#define CAN_RAW 1
#define SOL_CAN_RAW 101
#define CAN_RAW_FILTER 1

#define SOCK_RAW 3
#define SOCK_NONBLOCK 04000

struct can_frame {
    uint32_t can_id;
    uint8_t can_dlc;
    uint8_t __pad;
    uint8_t __res0;
    uint8_t __res1;
    uint8_t data[8];
};

struct can_filter {
    uint32_t can_id;
    uint32_t can_mask;
};

struct sockaddr_can {
    uint16_t can_family;
    int can_ifindex;
};

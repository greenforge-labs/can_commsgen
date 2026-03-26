cmake_minimum_required(VERSION 3.16)
project(can_commsgen_roundtrip_test CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The generated header is placed here by the test runner.
# The stub linux/can.h lives alongside this CMakeLists.txt.
set(GENERATED_DIR "${CMAKE_CURRENT_SOURCE_DIR}/generated")

add_executable(test_roundtrip test_roundtrip.cpp)

# Include path order matters: the stub directory (this dir) provides
# linux/can.h, and GENERATED_DIR provides can_messages.hpp.
target_include_directories(test_roundtrip PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${GENERATED_DIR}
)

# Compile-only target for can_interface.cpp.
# Uses stub system headers (poll.h, sys/socket.h, etc.) from this directory.
# Not linked into a runnable executable — just verifies the generated code compiles.
add_library(can_interface OBJECT ${GENERATED_DIR}/can_interface.cpp)
target_include_directories(can_interface PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${GENERATED_DIR}
)

enable_testing()
add_test(NAME roundtrip COMMAND test_roundtrip)

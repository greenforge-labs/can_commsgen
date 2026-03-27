cmake_minimum_required(VERSION 3.16)
project(can_commsgen_cpp_tests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The generated headers/sources are placed here by the Python test runner. The stub system headers (linux/can.h, poll.h,
# etc.) live alongside this CMakeLists.txt.
set(GENERATED_DIR "${CMAKE_CURRENT_SOURCE_DIR}/generated")

# --- roundtrip: pack/unpack correctness for can_messages.hpp -----------------
add_executable(test_roundtrip test_roundtrip.cpp)
target_include_directories(test_roundtrip PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${GENERATED_DIR})

# --- can_interface: runtime tests for the generated CanInterface class -------
add_executable(test_can_interface test_can_interface.cpp ${GENERATED_DIR}/can_interface.cpp)
target_include_directories(test_can_interface PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${GENERATED_DIR})

enable_testing()
add_test(NAME roundtrip COMMAND test_roundtrip)
add_test(NAME can_interface COMMAND test_can_interface)

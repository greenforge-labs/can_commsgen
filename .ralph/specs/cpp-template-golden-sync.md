# C++ Template & Generator Sync with Golden Files

## Problem

The golden files in `tests/golden/cpp/` have been updated with two categories of changes:

1. **Hardened SocketCAN patterns** in `can_interface.hpp` and `can_interface.cpp` — the golden files now reflect production-quality socket handling (errno diagnostics, EAGAIN/EINTR handling, move semantics, direct `socket_fd_` member instead of pimpl).
2. **clang-format conformance** across all three C++ golden files (`can_messages.hpp`, `can_interface.hpp`, `can_interface.cpp`) — includes are sorted alphabetically, column-alignment padding is removed, function parameters fit on single lines within 120 columns, `public:`/`private:` use 2-space indent per LLVM style.

The Jinja2 templates and the Python code in `cpp.py` that builds template context still generate the old code. Snapshot tests fail because generated output no longer matches the golden files.

## Goal

Update the C++ Jinja2 templates and `cpp.py` so that `generate_cpp()` produces output that matches the golden files byte-for-byte. All snapshot tests pass.

## Scope

### `can_messages.hpp.j2` + `cpp.py` parse/build line generation

The template and the Python functions `_parse_lines()` and `_build_lines()` in `cpp.py` need these changes to match the golden `can_messages.hpp`:

**Template changes (`can_messages.hpp.j2`)**:
- **Include order**: Change to `<cmath>`, `<cstdint>`, `<linux/can.h>`, `<optional>` (alphabetical, system headers sorted — `<linux/can.h>` before `<optional>`)
- **`extract_bits` signature**: Put all parameters on a single line — `inline int64_t extract_bits(const uint8_t data[8], uint16_t bit_offset, uint16_t bit_count, bool is_signed)` (fits within 120 col)
- **`insert_bits` signature**: Same — all parameters on one line
- **Remove `bit_idx` column alignment**: Change `uint16_t bit_idx  = ...` (two spaces) to `uint16_t bit_idx = ...` (one space) inside both helper functions
- **Guard conditions on separate lines**: Change `if (...) return std::nullopt;` to two-line form:
  ```cpp
  if (...)
      return std::nullopt;
  ```
- **Remove `frame.can_id  =` double space**: Change to single space `frame.can_id = ...`

**`cpp.py` changes — `_parse_lines()`**:
- Remove column-alignment padding on assignment left-hand sides (`msg.X = ...` not `msg.X     = ...`)
- Remove offset padding (no extra space before offset values like `0,  16` — use `0, 16`)
- For integer/enum types where `static_cast` wraps `extract_bits`: put the entire expression on one line instead of two indented lines. E.g. `msg.fault_code = static_cast<uint8_t>(detail::extract_bits(frame.data, 38, 8, false));` on a single line
- Remove closing-paren alignment padding (`signed_str)` ljust)

**`cpp.py` changes — `_build_lines()`**:
- Remove offset padding (no extra space: `0, 16` not `0,  16`)
- Remove `frame.can_id  =` double-space

**`cpp.py` changes — `_enum_data()`**:
- Remove `ljust(max_name_len)` padding on enum value names. The golden file shows no column alignment: `IDLE = 0` not `IDLE     = 0`

**`cpp.py` changes — `_message_data()` struct members**:
- Remove column alignment on member comments. Each member line should be `type name; // comment` with exactly one space before `//`, not padded to align comments across members. Exception: same-type members with similar comment lengths may naturally align — match the golden file exactly.

### `can_interface.hpp.j2`

The template needs these changes to match the golden `can_interface.hpp`:

- **Include order**: `"can_messages.hpp"` first, then sorted angle brackets: `<chrono>`, `<functional>`, `<linux/can.h>`, `<string>`, `<vector>`. Remove `<memory>` (pimpl removed).
- **Access specifiers**: `  public:` and `  private:` with 2-space indent (clang-format LLVM `AccessModifierOffset: -2` from 4-space indent)
- **Add move operations**: After the deleted copy operations, add:
  ```cpp
  CanInterface(CanInterface &&other) noexcept;
  CanInterface &operator=(CanInterface &&other) noexcept;
  ```
- **Remove pimpl**: Delete `struct Impl; std::unique_ptr<Impl> impl_;`. Replace with `int socket_fd_ = -1;`
- **Remove timeout state structs**: Delete the `MessageTimeoutState` struct definition and `*_timeout_state_` members from the template. (Timeout tracking was part of pimpl and is removed in the hardened version.)

### `can_interface.cpp.j2`

The template needs substantial changes to match the golden `can_interface.cpp`:

**Include order**: `"can_interface.hpp"` first, then sorted system headers: `<cstring>`, `<errno.h>`, `<linux/can/raw.h>`, `<net/if.h>`, `<poll.h>`, `<stdexcept>`, `<sys/ioctl.h>`, `<sys/socket.h>`, `<unistd.h>`

**Remove pimpl struct**: Delete `struct CanInterface::Impl { int socket_fd = -1; };`

**Constructor**:
- Initializer list: `: handlers_(std::move(handlers))` only (no `impl_`)
- Use `socket_fd_` directly instead of `impl_->socket_fd`
- Error messages include `strerror(errno)`: `"Failed to create CAN socket: " + std::string(strerror(errno))`
- `struct ifreq ifr;` without value-init (not `ifr{}`)
- Add null termination after strncpy: `ifr.ifr_name[IFNAMSIZ - 1] = '\0';`
- Error on ioctl includes device name and errno
- **Bind before setsockopt** (order swapped from original template)
- setsockopt has error checking — if it returns `< 0`, close socket and throw
- Long `setsockopt` condition wraps per clang-format `BlockIndent`:
  ```cpp
  if (setsockopt(socket_fd_, SOL_CAN_RAW, CAN_RAW_FILTER, filters.data(), filters.size() * sizeof(can_filter)) <
      0) {
  ```

**Destructor**: `if (socket_fd_ >= 0)` instead of `if (impl_ && impl_->socket_fd >= 0)`

**Move constructor and move assignment**: Add these implementations:
```cpp
CanInterface::CanInterface(CanInterface &&other) noexcept
    : socket_fd_(other.socket_fd_), handlers_(std::move(other.handlers_)) {
    other.socket_fd_ = -1;
}

CanInterface &CanInterface::operator=(CanInterface &&other) noexcept {
    if (this != &other) {
        if (socket_fd_ >= 0) {
            close(socket_fd_);
        }
        socket_fd_ = other.socket_fd_;
        handlers_ = std::move(other.handlers_);
        other.socket_fd_ = -1;
    }
    return *this;
}
```

**`process_frames()`**:
- Use `socket_fd_` directly
- Proper error handling on `read()`:
  - `if (n < 0)`: check `EAGAIN`/`EWOULDBLOCK` (break), `EINTR` (continue), else throw with `strerror(errno)`
  - `if (n != static_cast<ssize_t>(sizeof(frame)))`: throw "Incomplete CAN frame received"
- Switch case indentation: `case` at same indent as `switch` (clang-format):
  ```cpp
  switch (id) {
  case 0x00000200:
      ...
      break;
  }
  ```
- `if (parsed)` on separate line from handler call

**`wait_readable()`**: Use `socket_fd_` directly

**`send()` overloads**: Use `socket_fd_` directly. Error messages include message name and `strerror(errno)`: `"Failed to send motor_command: " + std::string(strerror(errno))`

**`compute_filters()`**: Use `socket_fd_`... wait, this function doesn't use the socket. Keep as-is but verify.

**`check_timeouts()`**: No change needed (already has `/*now*/` variant for no-timeout schemas).

### `tests/cpp_tests/` stubs

The C++ test stubs may need updates to support the new `errno` usage and `<linux/can/raw.h>` include. Verify that the stub headers define `errno`, `strerror`, `EAGAIN`, `EWOULDBLOCK`, `EINTR`, `ssize_t`, `SOL_CAN_RAW`, `CAN_RAW_FILTER`. If not, update the stubs.

## What NOT to change

- Golden files — these are the source of truth; the templates must match them
- `schema.py`, `plc.py`, `report.py` — unrelated
- PLC templates — unrelated
- `design.md`
- Test logic in `test_cpp_gen.py`, `test_integration.py`, `test_cli.py` — the tests should pass once generation matches golden files, no test changes needed

## Verification

1. `pixi run pytest tests/test_cpp_gen.py -v` — all C++ snapshot tests pass
2. `pixi run pytest tests/test_integration.py -v` — all integration tests pass
3. `pixi run pytest tests/ -v` — full suite green
4. `pixi run pyright can_commsgen/` — no type errors
5. `pixi run ruff check can_commsgen/ tests/` — no lint errors

# Implementation Plan

**Status**: All 95 tests passing. C++ templates aligned with hardened, clang-formatted golden files.

---

## Phase 10: Fix C++ Template / Golden File Divergence

> **Goal**: Update the Jinja2 templates and `cpp.py` so the generator produces output that matches the hardened, clang-formatted golden files byte-for-byte. All 95 tests green.

### 10.1 — Align `can_messages.hpp.j2` template with clang-formatted golden file

- [x] **10.1.1 Fix include ordering** — Change template to emit includes in clang-format alphabetical order: `<cmath>`, `<cstdint>`, `<linux/can.h>`, `<optional>` (clang-format sorts `<>` includes alphabetically).
  - *Why*: clang-format reorders includes; the template must emit them in the order clang-format produces so golden files match without post-processing.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.1.2 Remove manual alignment from enum entries** — In `_enum_data()` in `cpp.py`, stop left-justifying enum value names (currently `IDLE     = 0`). Emit `IDLE = 0` (single space).
  - *Why*: clang-format strips alignment padding in enum initialiser lists.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.1.3 Remove extra alignment from struct member comments** — In `_struct_members()` in `cpp.py`, change `ljust(max_decl_len)` + double-space to single-space before `//` comment. Golden file has e.g. `double target_velocity_rpm; // ...` with one space, not alignment padding.
  - *Why*: clang-format normalises whitespace before trailing comments.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.1.4 Remove alignment padding from parse/build function bodies** — In `_parse_lines()` and `_build_lines()` in `cpp.py`, remove `ljust()` alignment of offsets, bit counts, LHS assignments. Golden file uses compact single-space formatting.
  - *Why*: clang-format doesn't preserve hand-aligned columns in function bodies.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.1.5 Adjust line-break style in parse functions** — In the template, change `if (...) return std::nullopt;` to break onto separate lines:
  ```cpp
  if (...)
      return std::nullopt;
  ```
  The golden file (post-clang-format) puts the return on a new line.
  - *Why*: clang-format wraps single-line if+return when the line is short enough to warrant a break.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.1.6 Adjust line-break style in build functions** — Fix `frame.can_id  =` (double space) to `frame.can_id =` (single space). clang-format normalises alignment assignment whitespace.
  - *Why*: Golden file has single-space around `=` in assignments.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

### 10.2 — Rewrite `can_interface.hpp.j2` to match hardened golden file

- [x] **10.2.1 Remove pimpl, add direct socket_fd_ member** — Replace `struct Impl; std::unique_ptr<Impl> impl_;` with `int socket_fd_ = -1;`. Remove `<memory>` include.
  - *Why*: The hardened golden file uses a direct fd member for simplicity and move semantics.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_hpp_generation` passes.

- [x] **10.2.2 Add move constructor and move assignment** — Add declarations for `CanInterface(CanInterface &&other) noexcept;` and `CanInterface &operator=(CanInterface &&other) noexcept;` after the deleted copy operations.
  - *Why*: Hardened design supports move semantics for ownership transfer of the socket fd.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_hpp_generation` passes.

- [x] **10.2.3 Fix include ordering** — Emit includes in clang-format order: `"can_messages.hpp"` first (quoted), then `<chrono>`, `<functional>`, `<linux/can.h>`, `<string>`, `<vector>`.
  - *Why*: clang-format sorts quoted includes before angle-bracket includes, then alphabetically.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_hpp_generation` passes.

- [x] **10.2.4 Fix access specifier indentation** — Change `public:` / `private:` to clang-format style with 2-space indent: `  public:` / `  private:`.
  - *Why*: Golden file uses clang-format's default access specifier indentation.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_hpp_generation` passes.

- [x] **10.2.5 Remove timeout state struct and pimpl from template** — The hardened golden file for the example schema has no timeout state members (drive_status has no `timeout_ms`). The template conditionally emits these — verify they are correctly omitted. Also remove the `<memory>` include and `Impl` forward declaration.
  - *Why*: Aligns template with the non-pimpl design in golden files.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_hpp_generation` passes.

### 10.3 — Rewrite `can_interface.cpp.j2` to match hardened golden file

- [x] **10.3.1 Remove Impl struct and switch to direct socket_fd_** — Remove `struct CanInterface::Impl { ... };`. Replace all `impl_->socket_fd` with `socket_fd_`. Replace `impl_(std::make_unique<Impl>())` in initialiser list with direct init.
  - *Why*: Matches the non-pimpl hardened design.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.2 Add errno to error messages** — Change all `throw std::runtime_error("...")` calls to append `+ std::string(strerror(errno))`. Add `#include <errno.h>` and `#include <linux/can/raw.h>`.
  - *Why*: The hardened golden file provides errno context in all socket error messages for debuggability.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.3 Add null-terminate after strncpy** — After `std::strncpy(ifr.ifr_name, ...)`, add `ifr.ifr_name[IFNAMSIZ - 1] = '\0';`. Change `struct ifreq ifr{};` to `struct ifreq ifr;` (the null-terminate makes value-init unnecessary).
  - *Why*: Defence against non-null-terminated device names; matches hardened golden file.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.4 Reorder bind before setsockopt** — Move the `bind()` call before `compute_filters()` + `setsockopt()`. Add error check on `setsockopt` (currently unchecked). Both bind and setsockopt failures should close the socket and throw with errno.
  - *Why*: The hardened golden file binds first, then sets filters. Also adds error checking on setsockopt which was previously fire-and-forget.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.5 Add move constructor and assignment implementation** — Add `CanInterface::CanInterface(CanInterface &&other) noexcept` and `operator=(CanInterface &&other) noexcept` implementations that transfer `socket_fd_` and `handlers_`, setting source fd to -1.
  - *Why*: Matches the move-semantic design in the hardened golden file.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.6 Harden process_frames read loop** — Replace `if (n != sizeof(frame)) break;` with proper errno handling: EAGAIN/EWOULDBLOCK → break, EINTR → continue, other → throw. Add ssize_t cast for size comparison.
  - *Why*: The simple break-on-short-read doesn't distinguish non-blocking "no data" from actual errors.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.7 Fix destructor — remove impl_ check** — Change `if (impl_ && impl_->socket_fd >= 0)` to `if (socket_fd_ >= 0)`.
  - *Why*: No more pimpl; direct fd member is always valid.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.8 Fix include ordering** — Emit in clang-format order: `"can_interface.hpp"` first, then `<cstring>`, `<errno.h>`, `<linux/can/raw.h>`, `<net/if.h>`, `<poll.h>`, `<stdexcept>`, `<sys/ioctl.h>`, `<sys/socket.h>`, `<unistd.h>`.
  - *Why*: Matches clang-format alphabetical sorting.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.9 Fix switch/case indentation and single-line style** — Change `case` indentation from extra-indented to flush with `switch`. Change `if (parsed) handlers_.on_*(*parsed);` to two-line form per clang-format.
  - *Why*: clang-format uses Allman-ish case indentation (cases at switch level, body indented from case).
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.10 Add message name to send error messages** — Change `"Failed to send {{ msg.name }}"` to `"Failed to send {{ msg.name }}: " + std::string(strerror(errno))`.
  - *Why*: Consistent errno reporting across all error paths.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

- [x] **10.3.11 Move `now` timestamp after the read loop** — In `process_frames`, get `auto now = std::chrono::steady_clock::now();` after the for loop (not before). The hardened golden file calls `check_timeouts(now)` after the loop with a fresh timestamp.
  - *Why*: The hardened file gets the timestamp after draining frames for more accurate timeout detection.
  - *Test*: `tests/test_cpp_gen.py::test_can_interface_cpp_generation` passes.

### 10.4 — Update `cpp.py` generator logic

- [x] **10.4.1 Remove alignment padding from `_parse_lines()`** — Stop using `ljust()` to align offsets, bits, signed params, and LHS assignments. Emit compact formatting matching the clang-formatted golden file.
  - *Why*: clang-format strips manual alignment; output must match.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.4.2 Remove alignment padding from `_build_lines()`** — Same as above for insert_bits calls.
  - *Why*: Same clang-format reason.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.4.3 Remove alignment padding from `_struct_members()`** — Use single space before `//` comment instead of aligned columns.
  - *Why*: clang-format normalises trailing comment whitespace.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

- [x] **10.4.4 Remove alignment padding from `_enum_data()`** — Stop ljust-ing enum names.
  - *Why*: clang-format uses compact spacing.
  - *Test*: `tests/test_cpp_gen.py::test_can_messages_hpp_generation` passes.

### 10.5 — Verify integration and roundtrip tests

- [x] **10.5.1 Run full test suite** — All 95 tests pass after template updates. The C++ roundtrip compilation must succeed with the updated generated code.
  - *Why*: Ensures the template changes don't break compilation or introduce logic errors.
  - *Test*: `pixi run pytest tests/` — all green.

- [x] **10.5.2 Update `tests/cpp_tests/generated/` files** — Regenerate the C++ files in `tests/cpp_tests/generated/` using the CLI so they match the new template output. These are used by the C++ roundtrip build.
  - *Why*: The roundtrip tests compile files from this directory; they must reflect the current generator output.
  - *Test*: `tests/test_cpp_gen.py::test_cpp_roundtrip` passes. `tests/test_integration.py::test_cpp_roundtrip_via_cli` passes.

### 10.6 — Clean up stale `tests/cpp_roundtrip/` directory

- [x] **10.6.1 Remove or .gitignore `tests/cpp_roundtrip/`** — This directory is untracked (`?? tests/cpp_roundtrip/` in git status) and appears to be a leftover from before `tests/cpp_tests/` was created. No test code references it. Verify nothing references it, then delete or add to `.gitignore`.
  - *Why*: Prevents confusion about which C++ test directory is authoritative.
  - *Test*: `pixi run pytest tests/` still all green after removal.

---

## Notes

- **clang-format as source of truth for C++ style**: Since the precommit hook runs clang-format on all C++ files (including golden files), the templates must produce output that is already clang-format-stable. An alternative would be to exclude golden files from clang-format (via `.clang-format-ignore`), but matching the format is cleaner long-term since the generated code in consuming repos will also be formatted.
- **Scope**: Only `can_messages.hpp.j2`, `can_interface.hpp.j2`, `can_interface.cpp.j2`, and `cpp.py` need changes. No schema model, PLC, report, or CLI changes.
- **Items 10.1–10.4 can be done together**: Most of these are closely coupled changes to the same files. They're listed separately for tracking but should be implemented as a cohesive unit.
- **Golden file discipline**: Do NOT modify golden files — fix the templates and generator until output matches.
- **The existing `tests/cpp_tests/generated/` files** may need to be regenerated after template changes (10.5.2) since the roundtrip build compiles from that directory.

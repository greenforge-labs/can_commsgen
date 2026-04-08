# CAN Interface Generation

## Problem
Consumers of the generated C++ need a ready-made SocketCAN wrapper that dispatches received frames to callbacks and provides typed send helpers. Without it, every consumer re-implements socket setup, filtering, frame dispatch, and timeout tracking.

## Goal
Extend `can_commsgen/cpp.py` (or add a new module) to generate two additional files alongside `can_messages.hpp`:
- `can_interface.hpp` — class declaration
- `can_interface.cpp` — implementation

A new Jinja2 template (or pair of templates) in `templates/cpp/` defines the output format. The existing `generate_cpp()` entrypoint (or a new function called from the CLI) writes these files to the same output directory.

## Scope

### Generated class: `CanInterface` (namespace `project_can`)

#### `Handlers` struct
- One `std::function<void(StructName)> on_{msg_name}` per `plc_to_pc` message (data callback).
- One `std::function<void()> on_{msg_name}_timeout` per `plc_to_pc` message **that has `timeout_ms`** (edge-triggered timeout callback).
- `pc_to_plc` messages get no handlers — they are sent, not received.
- A message is added to the socket filter if *either* its data or timeout handler is non-null.

#### Constructor / destructor
- `CanInterface(std::string can_device, Handlers handlers)` — creates and configures the SocketCAN socket (extended frames, non-blocking), applies filters derived from non-null handlers.
- `~CanInterface()` — closes socket via pimpl (`std::unique_ptr<Impl>`).

#### `process_frames(size_t max_frames = 5)`
- Non-blocking: reads up to `max_frames` from the socket.
- For each frame, matches CAN ID and calls the corresponding `parse_*` + data handler.
- After draining, calls `check_timeouts()` for messages with a non-null timeout handler.
- Returns immediately if no frames available.

#### `wait_readable()`
- Blocks on `poll()` until the socket has data (or is closed).
- For dedicated receive thread use: `while (running) { can.wait_readable(); can.process_frames(); }`

#### `send()` overloads
- One `void send(const StructName &msg)` per `pc_to_plc` message.
- Calls the corresponding `build_*` function and writes to the socket.
- Propagates `std::runtime_error` on socket failure.

#### Timeout tracking (private)
- Per-message `MessageTimeoutState` struct: `timeout` (from YAML `timeout_ms`), `last_received`, `timed_out` flag.
- Generated as named members (e.g. `drive_status_timeout_state_`), not a container.
- Edge-triggered: fires once on entering timeout, resets when the message arrives again.

#### Private implementation
- `std::vector<can_filter> compute_filters() const` — builds filter list from non-null handlers.
- `void check_timeouts(std::chrono::steady_clock::time_point now)` — scans timeout states.
- `struct Impl` behind `std::unique_ptr<Impl>` holds the socket fd.

### Key generation rules
- Include guards, `#pragma once`, `// THIS FILE IS AUTO-GENERATED. DO NOT EDIT.`
- `can_interface.hpp` includes `<chrono>`, `<functional>`, `<string>`, `<linux/can.h>`, `"can_messages.hpp"`
- `can_interface.cpp` includes `<poll.h>`, `<sys/socket.h>`, `<sys/ioctl.h>`, `<net/if.h>`, `<unistd.h>`, `<cstring>`, `<stdexcept>`, `"can_interface.hpp"`
- Struct/message names follow existing C++ naming from `can_messages.hpp` (PascalCase structs, snake_case functions)

### NOT in scope
- Modifying `can_messages.hpp` generation
- Schema model changes (all required data is already in the normalised model)
- PLC generation

## What NOT to change
- Golden files for existing generators
- `schema.py`, `plc.py`, `report.py`
- `design.md`

## Testing
- Snapshot test: generate from `tests/fixtures/example_schema.yaml`, compare against new golden files in `tests/golden/cpp/can_interface.hpp` and `tests/golden/cpp/can_interface.cpp`
- Test in `tests/test_cpp_gen.py` alongside existing C++ generation tests
- The generated code must compile (verified by extending the existing C++ roundtrip build in `tests/cpp_tests/` to include the new files, though linking against SocketCAN APIs will require stubs or compile-only checks on CI)

# can_commsgen

CAN YAML schema → PLC Structured Text + C++ code generator.

## Specs
Read all files in `.ralph/specs/` (excluding `_archive/`) for the full specification:
- `.ralph/specs/project-scaffolding.md` — Python package setup, deps, directory structure
- `.ralph/specs/schema-model.md` — YAML loading, validation, wire type inference, bitpacking
- `.ralph/specs/plc-generation.md` — Jinja2 templates and generation for all PLC ST outputs
- `.ralph/specs/cpp-generation.md` — Jinja2 template and generation for can_messages.hpp
- `.ralph/specs/packing-report.md` — Human-readable packing report generation
- `.ralph/specs/cli.md` — Click CLI entrypoint

## Design Document
`design.md` is the authoritative specification. When in doubt, refer to it.

## Operational Guide
Read `.ralph/AGENTS.md` for commands, conventions, and known gotchas.

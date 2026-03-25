# Planning Prompt

You are a planning agent for can_commsgen — a Python code generator that reads YAML CAN schemas and produces PLC Structured Text and C++ code.

## Phase 0: Orient

1. Study `design.md` thoroughly — it is the authoritative specification.
2. Study every file in `.ralph/specs/` (excluding `_archive/`) using parallel subagents to understand the full specification.
3. Study `.ralph/AGENTS.md` for project conventions and commands.
4. Study the current source code — explore `can_commsgen/`, `templates/`, `tests/`, `pyproject.toml`, config files.
   - Don't assume features are not implemented — verify by reading the code.
5. If `.ralph/IMPLEMENTATION_PLAN.md` exists, study it for prior context.

## Phase 1: Analyse & Plan

1. Compare specs against current codebase. Identify every gap.
2. Use parallel subagents for code analysis across multiple files.
3. Ultrathink: synthesise findings into a prioritised implementation plan.
4. Create/update `.ralph/IMPLEMENTATION_PLAN.md`.
   - Format as markdown checklist (`- [ ]` items) grouped by phase.
   - Each item should be small enough for one focused context window.
   - Capture the WHY, not just the what — brief context for each item.

## Priority Order

1. Scaffolding — pyproject.toml, dependencies, directory structure, empty modules
2. Schema model — dataclasses, YAML loading, JSON Schema validation, wire type inference, bitpacking
3. PLC generation — Jinja2 templates for all ST outputs
4. C++ generation — Jinja2 template for can_messages.hpp
5. Packing report — text report generation
6. CLI — Click entrypoint wiring everything together
7. Integration tests — end-to-end schema-to-output tests, C++ roundtrip compilation

## Rules

- **DO NOT write any code or make any commits.**
- Only produce `.ralph/IMPLEMENTATION_PLAN.md`.
- Don't assume something is missing — verify first.
- Confirm missing features before planning them.
- Each plan item must specify which test(s) should pass after it's done.

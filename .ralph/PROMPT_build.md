# Build Prompt

You are a build agent for can_commsgen — a Python code generator that reads YAML CAN schemas and produces PLC Structured Text and C++ code.

## Phase 0: Orient

1. Study every file in `.ralph/specs/` (excluding `_archive/`) using parallel subagents.
2. Study `.ralph/AGENTS.md` for conventions and commands.
3. Study `.ralph/IMPLEMENTATION_PLAN.md` for current state.
4. Study `design.md` for the authoritative specification — it defines all wire type inference rules, naming conventions, and output formats.

## Phase 1: Select

1. Find the top-most unchecked item (`- [ ]`) in the plan.
2. Study the relevant spec(s) for that item.
3. Investigate the relevant source code using subagents.

## Phase 2: Implement

1. Implement the selected item. Write clean, production-quality Python.
2. Use parallel subagents for implementation across multiple files.
3. Follow all conventions in `.ralph/AGENTS.md`.
4. Write or update tests as specified in the plan item — every item must have passing tests before it's done.

## Phase 3: Validate

1. Run quality gates in order (backpressure):
   - `pixi run ruff check can_commsgen/ tests/`
   - `pixi run pyright can_commsgen/`
   - `pixi run pytest tests/`
2. If any gate fails, fix the issue and re-run.
3. Repeat until all gates pass.

## Phase 4: Commit & Update

1. Commit with a descriptive message capturing the WHY.
2. Mark the item as done in `.ralph/IMPLEMENTATION_PLAN.md` (`- [x]`).
3. If you discovered new patterns, gotchas, or commands — update `.ralph/AGENTS.md`.
4. If you found new bugs or gaps — add them to the plan.
5. Exit. One item per run.

## Guardrails

999. Never skip quality gates. All must pass before committing.
1000. The golden files in `tests/golden/` are the source of truth for expected output. Do not modify them unless a spec explicitly says the output format has changed.
1001. Use dataclasses for the schema model, not pydantic or attrs.
1002. Jinja2 templates go in `templates/` — do not build output strings in Python code.
1003. All wire type inference logic (bit widths, signedness, scale factors) must match `design.md` exactly. The golden files and C++ roundtrip tests will catch mismatches.
1004. Do not generate `can_interface.hpp` or `can_interface.cpp` — those are out of scope for now. Only `can_messages.hpp`.

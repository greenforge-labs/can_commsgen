# Agents

## Commands
| Task       | Command                                                                                     |
|------------|---------------------------------------------------------------------------------------------|
| Install    | `pixi install`                                                                              |
| Test       | `pixi run pytest tests/`                                                                    |
| Typecheck  | `pixi run pyright can_commsgen/`                                                            |
| Lint       | `pixi run ruff check can_commsgen/ tests/`                                                  |
| C++ test   | See tests/cpp_tests/CMakeLists.txt — build and run after generating into generated/ dir  |

## Quality Gates (run in order)
1. `pixi run ruff check can_commsgen/ tests/`
2. `pixi run pyright can_commsgen/`
3. `pixi run pytest tests/`

## Conventions
- Python 3.11+, use dataclasses for the schema model (not pydantic)
- Jinja2 templates live in `templates/plc/` and `templates/cpp/`
- Golden files in `tests/golden/` are the expected generator output — do not modify unless intentionally changing output format
- Test fixtures in `tests/fixtures/`
- The C++ roundtrip test in `tests/cpp_tests/` compiles and runs the generated C++ to prove bitpacking correctness

## Gotchas
_None yet — agent will populate this section._

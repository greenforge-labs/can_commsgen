# Project Scaffolding

## Problem
No Python package structure exists yet — just a design doc, golden files, and a C++ roundtrip test harness.

## Goal
A working Python package that can be installed via pixi, with all dependencies declared, empty modules in place, and quality gates (ruff, pyright, pytest) passing on the empty project.

## Scope
- `pyproject.toml` with project metadata, dependencies (pyyaml, jinja2, click), and dev dependencies (pytest, ruff, pyright)
- `pixi.toml` for environment management
- Directory structure: `can_commsgen/` package with `__init__.py`, `schema.py`, `plc.py`, `cpp.py`, `report.py`; `cli.py` at repo root (or as console_scripts entry point)
- `templates/plc/` and `templates/cpp/` directories (empty template files are fine)
- `tests/conftest.py` with a fixture that loads `tests/fixtures/example_schema.yaml`
- A minimal `tests/test_schema.py` with one placeholder test that passes

## What NOT to change
- Do not modify golden files in `tests/golden/`
- Do not modify `tests/cpp_roundtrip/` files
- Do not modify `design.md`

## Testing
After this is done: `pixi install && pixi run ruff check can_commsgen/ tests/ && pixi run pyright can_commsgen/ && pixi run pytest tests/` should all pass (on the empty/placeholder project).

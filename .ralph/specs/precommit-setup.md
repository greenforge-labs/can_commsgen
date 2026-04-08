# Pre-commit Hook Installation

## Problem

The project has a `.pre-commit-config.yaml` and formatting configuration (`.clang-format`, `.cmake-format`, `pyproject.toml` `[tool.black]`/`[tool.isort]` sections) already committed. However, the pre-commit hooks are not installed in the local git repo. A developer (or the loop agent) needs to run `pre-commit install` to activate the hooks so they run automatically on `git commit`.

## Goal

Ensure pre-commit hooks are installed in the local repo so that every `git commit` automatically runs black, isort, clang-format, cmake-format, and the standard pre-commit-hooks checks. This prevents formatting drift from entering the repo.

## Scope

### Install pre-commit hooks

Run `pixi run pre-commit install` (or `pre-commit install` if pre-commit is available on PATH). This creates `.git/hooks/pre-commit` pointing at the pre-commit framework.

### Verify pre-commit is available

The `pixi.toml` environment should include `pre-commit` as a dependency. If it doesn't, add it. Check `pixi.toml` for a `[dependencies]` or `[feature.*.dependencies]` section that includes `pre-commit`. If missing, add `pre-commit` to the pixi environment.

### Run pre-commit against all files

After installation, run `pixi run pre-commit run --all-files` to verify all hooks pass on the current codebase. If any hook fails, fix the files (the formatters auto-fix, so re-staging and re-running should suffice). The codebase was already formatted in commit `6d53415`, so this should be a no-op — but verify.

## What NOT to change

- `.pre-commit-config.yaml` — already correct
- `.clang-format`, `.cmake-format` — already correct
- `pyproject.toml` `[tool.black]`/`[tool.isort]` sections — already correct
- Any source code (unless pre-commit finds unformatted files, in which case apply the formatter fix)

## Verification

1. `.git/hooks/pre-commit` exists and references pre-commit
2. `pixi run pre-commit run --all-files` exits 0

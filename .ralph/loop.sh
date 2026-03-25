#!/usr/bin/env bash
set -euo pipefail

RALPH_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_ITERATIONS=20
MODE="build"

usage() {
  echo "Usage: $0 [--plan] [--max-iterations N]"
  echo ""
  echo "  --plan              Run planning mode (generate IMPLEMENTATION_PLAN.md)"
  echo "  --max-iterations N  Maximum loop iterations (default: $MAX_ITERATIONS)"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)   MODE="plan"; shift ;;
    --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

CURRENT_BRANCH=$(git branch --show-current)

if [[ "$MODE" == "plan" ]]; then
  echo "=== Running planning mode ==="
  cat "$RALPH_DIR/PROMPT_plan.md" | claude -p \
    --dangerously-skip-permissions \
    --output-format=stream-json \
    --verbose
  git push origin "$CURRENT_BRANCH"
  echo "=== Planning complete ==="
  exit 0
fi

echo "=== Starting build loop (max $MAX_ITERATIONS iterations) ==="

for ((i = 1; i <= MAX_ITERATIONS; i++)); do
  echo ""
  echo "--- Iteration $i / $MAX_ITERATIONS ---"

  # Check if there are unchecked items remaining
  if ! grep -q '^\- \[ \]' "$RALPH_DIR/IMPLEMENTATION_PLAN.md" 2>/dev/null; then
    echo "=== All plan items complete! ==="
    exit 0
  fi

  cat "$RALPH_DIR/PROMPT_build.md" | claude -p \
    --dangerously-skip-permissions \
    --output-format=stream-json \
    --verbose

  # Push after each iteration so progress is durable
  git push origin "$CURRENT_BRANCH"

  echo "--- Iteration $i complete ---"
done

echo "=== Reached max iterations ($MAX_ITERATIONS). Stopping. ==="

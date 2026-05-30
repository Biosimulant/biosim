#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
elif [[ -x "$ROOT_DIR/.venv-check/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv-check/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "Missing Python executable. Create a venv, then install dev dependencies:" >&2
  echo "  python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

cd "$ROOT_DIR"

"$PYTHON" -m pytest tests/ \
  --tb=short \
  -q \
  --cov=biosim \
  --cov=biosimulant \
  --cov-report=term-missing \
  --cov-fail-under=82

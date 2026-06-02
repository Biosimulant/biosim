#!/usr/bin/env bash
set -euo pipefail

# Build the private labs-serve React UI into the Python package static dir.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/packages/labs-serve-ui"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Please install Node.js and npm." >&2
  exit 1
fi

cd "$FRONTEND_DIR"

if [[ -f package-lock.json || -f npm-shrinkwrap.json ]]; then
  echo "Installing labs-serve UI deps (npm ci)..."
  npm ci
else
  echo "No lockfile found. Installing labs-serve UI deps (npm install)..."
  npm install
fi

echo "Building labs-serve UI..."
npm run build

echo "Done."

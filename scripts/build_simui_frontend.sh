#!/usr/bin/env bash
set -euo pipefail

# Build the SimUI frontend (React/TS) and copy artifacts into the Python package static dir.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/packages/simui-ui"
STATIC_DIR="$ROOT_DIR/src/biosim/simui/static"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Please install Node.js and npm." >&2
  exit 1
fi

cd "$FRONTEND_DIR"

if [[ -f package-lock.json || -f npm-shrinkwrap.json ]]; then
  echo "Installing frontend deps (npm ci)..."
  npm ci
else
  echo "No lockfile found. Installing deps (npm install)..."
  npm install
fi

echo "Building frontend (npm run build:static)..."
npm run build:static

echo "Copying artifacts to $STATIC_DIR ..."
mkdir -p "$STATIC_DIR"
cp -f dist-static/app.js "$STATIC_DIR/app.js"
# Copy CSS bundle if present for additional styling
if [ -f dist-static/app.css ]; then
  cp -f dist-static/app.css "$STATIC_DIR/app.css"
fi

echo "Done."

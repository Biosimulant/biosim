#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/release_pypi.sh [VERSION] [--no-push]

Examples:
  bash scripts/release_pypi.sh
  bash scripts/release_pypi.sh 0.0.2
  bash scripts/release_pypi.sh --no-push
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

version=""
push=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --no-push)
      push=false
      shift
      ;;
    *)
      if [[ -z "$version" ]]; then
        version="$1"
        shift
      else
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  echo "Working tree must be clean (including untracked files) before releasing." >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "main" && "$branch" != "master" ]]; then
  echo "Release must run from main/master. Current branch: $branch" >&2
  exit 1
fi

current_version="$(python3 - <<'PY'
from pathlib import Path
ns = {}
exec(Path('src/biosim/__about__.py').read_text(), ns)
print(ns['__version__'])
PY
)"

if [[ -z "$version" ]]; then
  version="$current_version"
fi

if [[ "$version" != "$current_version" ]]; then
  echo "Version mismatch. __about__.py has $current_version but script was asked for $version." >&2
  echo "Update src/biosim/__about__.py first, commit, then rerun." >&2
  exit 1
fi

tag="v${version}"
if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
  echo "Tag ${tag} already exists locally." >&2
  exit 1
fi

if $push; then
  echo "Pushing ${branch} to origin..."
  git push origin "$branch"
fi

echo "Creating tag ${tag}..."
git tag "$tag"

if $push; then
  echo "Pushing tag ${tag} to origin..."
  git push origin "$tag"
fi

echo "Release tag ${tag} created."

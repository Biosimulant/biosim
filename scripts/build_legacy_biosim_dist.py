#!/usr/bin/env python3
"""Build legacy ``biosim`` PyPI distributions from the current source tree."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _copy_ignore(_path: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in {
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "build",
            "dist",
            "node_modules",
        }:
            ignored.add(name)
        elif name.endswith((".egg-info", ".pyc", ".pyo")):
            ignored.add(name)
    return ignored


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f"Expected text not found in pyproject.toml: {old!r}")
    return text.replace(old, new, 1)


def _prepare_legacy_metadata(worktree: Path) -> None:
    pyproject_path = worktree / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    pyproject = _replace_once(pyproject, 'name = "biosimulant"', 'name = "biosim"')
    pyproject = _replace_once(
        pyproject,
        'description = "Open-source local simulation runtime and CLI for Biosimulant"',
        'description = "Open-source local simulation runtime and CLI for Biosimulant (legacy biosim distribution)"',
    )
    pyproject = _replace_once(
        pyproject,
        'biosimulant = "biosimulant.__main__:main"',
        'biosim = "biosim.__main__:main"',
    )
    pyproject = _replace_once(
        pyproject,
        '"biosimulant[dev,ui,ml,cellml]"',
        '"biosim[dev,ui,ml,cellml]"',
    )
    pyproject_path.write_text(pyproject, encoding="utf-8")

    readme_path = worktree / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(
        "# biosim\n\n"
        "This is the legacy PyPI distribution name for Biosimulant. New projects "
        "should prefer `pip install biosimulant`; this package is published in "
        "lockstep and ships both the `biosim` and `biosimulant` import namespaces.\n\n"
        + readme,
        encoding="utf-8",
    )


def build_legacy_distribution(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="biosim-legacy-build-") as temp_dir:
        worktree = Path(temp_dir) / "src"
        shutil.copytree(ROOT_DIR, worktree, ignore=_copy_ignore)
        _prepare_legacy_metadata(worktree)
        subprocess.run(
            [sys.executable, "-m", "build", "--outdir", str(outdir.resolve())],
            cwd=worktree,
            check=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build legacy biosim PyPI distributions from this checkout."
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("dist/biosim"),
        help="Directory where the legacy biosim artifacts should be written.",
    )
    args = parser.parse_args(argv)

    build_legacy_distribution(args.outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

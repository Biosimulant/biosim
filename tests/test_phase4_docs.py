from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TEXT_ROOTS = (ROOT / "README.md", ROOT / "docs", ROOT / "examples")
COMPATIBILITY_DOCS = {
    ROOT / "README.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "releasing.md",
}


def _public_text_files() -> list[Path]:
    files: list[Path] = []
    for root in PUBLIC_TEXT_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.suffix in {".md", ".py"} and "__pycache__" not in path.parts
        )
    return sorted(files)


def test_public_docs_lead_with_biosimulant_package_and_cli() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")

    assert readme.startswith("# biosimulant")
    assert "`biosimulant` is the primary package, import namespace, and CLI name" in readme
    assert "pip install biosimulant" in readme
    assert "biosimulant labs init" in readme
    assert "pip install 'biosimulant[ui]'" in quickstart
    assert "biosimulant labs init" in quickstart


def test_legacy_biosim_command_is_only_documented_as_compatibility() -> None:
    legacy_command = re.compile(r"python -m biosim(\s|$)")
    offenders: list[str] = []
    for path in _public_text_files():
        text = path.read_text(encoding="utf-8")
        if legacy_command.search(text) and path not in COMPATIBILITY_DOCS:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_public_examples_do_not_use_legacy_install_or_cli_names() -> None:
    forbidden = (
        re.compile(r"pip install ['\"]?biosim(\[|\s|$)"),
        re.compile(r"\bbiosim labs\b"),
        re.compile(r"\bbiosim packages\b"),
        re.compile(r"\bbiosim pack\b"),
    )
    offenders: list[str] = []

    for path in _public_text_files():
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")

    assert offenders == []


def test_public_python_examples_import_primary_namespace() -> None:
    offenders: list[str] = []
    for path in _public_text_files():
        if path == ROOT / "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "import biosim" or stripped.startswith("from biosim "):
                offenders.append(f"{path.relative_to(ROOT)}: {stripped}")

    assert offenders == []

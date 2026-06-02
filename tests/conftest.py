from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure biosim is importable for both fixture-based and direct-import tests
_src = str(Path(__file__).resolve().parents[1] / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Also ensure examples dir is importable
_examples = str(Path(__file__).resolve().parents[1] / "examples")
if _examples not in sys.path:
    sys.path.insert(0, _examples)


@pytest.fixture(scope="session")
def biosim():
    import biosim as _bsim  # type: ignore
    return _bsim


@pytest.fixture(autouse=True)
def _disable_desktop_cli_delegation_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOSIMULANT_DISABLE_DESKTOP_DELEGATION", "1")

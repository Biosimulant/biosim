from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def biosim():
    try:
        import biosim as _bsim  # type: ignore
        return _bsim
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import biosim as _bsim  # type: ignore  # noqa: E402
        return _bsim

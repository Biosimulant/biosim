from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, Callable

import pytest


@pytest.fixture(scope="session")
def bsim():
    try:
        import bsim as _bsim  # type: ignore
        return _bsim
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import bsim as _bsim  # type: ignore  # noqa: E402
        return _bsim


@pytest.fixture()
def custom_solver(bsim):
    class CustomSolver(bsim.Solver):
        def simulate(self, *, steps: int, dt: float, emit: Callable[[Any, Dict[str, Any]], None]):
            state: Dict[str, Any] = {"time": 0.0, "steps": 0}
            for i in range(steps):
                state["time"] += dt
                state["steps"] = i + 1
                emit(bsim.BioWorldEvent.STEP, {"i": i, "t": state["time"]})
            return state

    return CustomSolver()


@pytest.fixture()
def failing_solver(bsim):
    class FailingSolver(bsim.Solver):
        def simulate(self, *, steps: int, dt: float, emit: Callable[[Any, Dict[str, Any]], None]):
            emit(bsim.BioWorldEvent.STEP, {"i": 0, "t": dt})
            raise RuntimeError("boom")

    return FailingSolver()

"""Tests for my_pack solvers."""
import pytest


def test_variable_step_solver_clamps_dt():
    """VariableStepSolver should clamp dt to bounds."""
    from my_pack import VariableStepSolver
    from bsim import BioWorldEvent

    solver = VariableStepSolver(min_dt=0.01, max_dt=0.05)

    events = []

    def emit(event, payload):
        events.append((event, payload))

    # dt=0.1 should be clamped to max_dt=0.05
    result = solver.simulate(steps=10, dt=0.1, emit=emit)

    assert len(events) == 10
    assert events[0][1]["dt"] == 0.05  # Clamped
    assert result["actual_dt"] == 0.05


def test_variable_step_solver_respects_min():
    """VariableStepSolver should respect min_dt."""
    from my_pack import VariableStepSolver

    solver = VariableStepSolver(min_dt=0.01, max_dt=0.1)

    events = []

    def emit(event, payload):
        events.append(payload)

    # dt=0.001 should be clamped to min_dt=0.01
    solver.simulate(steps=5, dt=0.001, emit=emit)

    assert events[0]["dt"] == 0.01  # Clamped to min


def test_variable_step_solver_overrides():
    """VariableStepSolver should support with_overrides."""
    from my_pack import VariableStepSolver

    solver = VariableStepSolver(min_dt=0.01, max_dt=0.1)

    # Override max_dt
    new_solver = solver.with_overrides({"max_dt": 0.02})

    assert new_solver is not solver  # New instance
    assert new_solver.max_dt == 0.02
    assert new_solver.min_dt == 0.01  # Unchanged


def test_variable_step_solver_no_change_override():
    """with_overrides should return self if no changes."""
    from my_pack import VariableStepSolver

    solver = VariableStepSolver(min_dt=0.01, max_dt=0.1)

    same_solver = solver.with_overrides({})

    assert same_solver is solver  # Same instance

"""Tests for biosim.modules default V2 method behavior."""

from __future__ import annotations


def _minimal_module(biosim):
    class Minimal(biosim.BioModule):
        def advance_window(self, _start, t):
            pass

        def get_outputs(self):
            return {}

    return Minimal()


def test_setup_default_noop(biosim):
    assert _minimal_module(biosim).setup() is None


def test_reset_default_noop(biosim):
    assert _minimal_module(biosim).reset() is None


def test_set_inputs_default_noop(biosim):
    result = _minimal_module(biosim).set_inputs(
        {"x": biosim.ScalarSignal("src", "x", 1.0, 0.0, spec=biosim.SignalSpec.scalar(dtype="float64"))}
    )
    assert result is None


def test_snapshot_default_empty(biosim):
    assert _minimal_module(biosim).snapshot() == {}


def test_restore_default_noop(biosim):
    assert _minimal_module(biosim).restore({}) is None


def test_inputs_default_empty_mapping(biosim):
    assert _minimal_module(biosim).inputs() == {}


def test_outputs_default_empty_mapping(biosim):
    assert _minimal_module(biosim).outputs() == {}


def test_visualize_default_none(biosim):
    assert _minimal_module(biosim).visualize() is None

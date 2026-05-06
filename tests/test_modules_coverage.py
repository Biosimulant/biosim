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


def test_signal_emitter_wraps_payloads(biosim):
    class Emitter(biosim.SignalEmitterBioModule):
        def outputs(self):
            return {"out": biosim.SignalSpec.record(schema={"payload": "json"})}

        def advance_window(self, start, end):
            self.publish_outputs(end, {"out": [1, 2]})

    module = Emitter()
    module.advance_window(0.0, 1.0)

    outputs = module.get_outputs()
    assert outputs["out"].source == "Emitter"
    assert outputs["out"].value == {"payload": [1, 2]}


def test_stateful_biomodule_runs_fixed_steps(biosim):
    class Counter(biosim.StatefulBioModule):
        def __init__(self):
            super().__init__(integration_step=0.25, record_initial_state=True)
            self.value = 0.0

        def outputs(self):
            return {"value": biosim.SignalSpec.scalar(dtype="float64")}

        def reset_state(self):
            self.value = 0.0

        def step(self, h):
            self.value += h

        def record_state(self, t):
            self._history.append({"t": t, "value": self.value})

        def output_payload(self, t):
            return {"value": self.value}

    module = Counter()
    result = module.advance_window(0.0, 1.0)

    assert module.value == 1.0
    assert len(module.history) == 5
    assert result["value"].value == 1.0
    assert result["value"].emitted_at == 1.0

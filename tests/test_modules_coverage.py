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


def test_signal_emitter_defaults_and_world_source_name(biosim):
    class Emitter(biosim.SignalEmitterBioModule):
        def advance_window(self, start, end):
            return

    module = Emitter()
    module._world_name = "alias"

    assert module.source_name() == "alias"
    assert module.output_payload(0.0) == {}
    module.publish_outputs(0.0)
    assert module.get_outputs() == {}
    module.publish_outputs(0.0, {"raw": 3})
    assert module.get_outputs()["raw"].source == "alias"
    module.clear_outputs()
    assert module.get_outputs() == {}


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


def test_stateful_biomodule_validates_constructor_arguments(biosim):
    class Counter(biosim.StatefulBioModule):
        def advance_window(self, start, end):
            return super().advance_window(start, end)

    import pytest

    with pytest.raises(ValueError, match="integration_step"):
        Counter(integration_step=0.0)
    with pytest.raises(ValueError, match="max_history_points"):
        Counter(max_history_points=0)


def test_stateful_biomodule_setup_zero_window_inputs_and_history_trim(biosim):
    class Counter(biosim.StatefulBioModule):
        def __init__(self):
            super().__init__(
                integration_step=0.5,
                max_history_points=2,
                record_initial_state=True,
                publish_on_setup=True,
                publish_on_zero_window=True,
            )
            self.value = 0.0
            self.override_calls = []

        def outputs(self):
            return {"value": biosim.SignalSpec.scalar(dtype="float64")}

        def reset_state(self):
            self.value = 1.0

        def apply_overrides(self, *, reset_initial_state):
            self.override_calls.append(reset_initial_state)
            signal = self._input_overrides.get("value")
            if signal is not None:
                self.value = float(signal.value)

        def step(self, h):
            self.value += h

        def record_state(self, t):
            self._history.append({"t": t, "value": self.value})

        def output_payload(self, t):
            return {"value": self.value}

    module = Counter()
    module.setup()
    assert module.get_outputs()["value"].value == 1.0

    output = module.advance_window(
        0.0,
        0.0,
        inputs={
            "value": biosim.ScalarSignal(
                source="test",
                name="value",
                value=5.0,
                emitted_at=0.0,
                spec=biosim.SignalSpec.scalar(dtype="float64"),
            )
        },
    )
    assert output["value"].value == 5.0
    assert module.override_calls[-1] is True

    module.advance_window(0.0, 2.0)
    assert module.history == [{"t": 1.5, "value": 6.5}, {"t": 2.0, "value": 7.0}]


def test_stateful_biomodule_can_skip_zero_window_publish(biosim):
    class Counter(biosim.StatefulBioModule):
        def __init__(self):
            super().__init__(publish_on_zero_window=False)

        def output_payload(self, t):
            return {"value": 1}

    module = Counter()

    assert module.advance_window(0.0, 0.0) == {}

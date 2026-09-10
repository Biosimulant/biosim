from __future__ import annotations

import threading

import pytest

import biosim
from biosimulant import ExecutionContext as PrimaryExecutionContext
from biosimulant import ExecutionPolicy as PrimaryExecutionPolicy


SCALAR = biosim.SignalSpec.scalar(dtype="float64")


def test_execution_api_is_exported_from_both_namespaces() -> None:
    assert PrimaryExecutionPolicy is biosim.ExecutionPolicy
    assert PrimaryExecutionContext is biosim.ExecutionContext


def test_execution_context_is_immutable_and_derives_simulated_time() -> None:
    before = biosim.ExecutionContext(
        policy=biosim.ExecutionPolicy.ONCE_BEFORE_RUN,
        run_start=2,
        run_end=5,
    )
    window = biosim.ExecutionContext(
        policy="each_window",
        run_start=2,
        run_end=5,
        window_start=3,
        window_end=4,
    )
    after = biosim.ExecutionContext(
        policy=biosim.ExecutionPolicy.ONCE_AFTER_RUN,
        run_start=2,
        run_end=5,
    )

    assert before.simulated_time == 2.0
    assert window.policy is biosim.ExecutionPolicy.EACH_WINDOW
    assert window.simulated_time == 4.0
    assert after.simulated_time == 5.0
    with pytest.raises((AttributeError, TypeError)):
        before.run_start = 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"policy": "bad", "run_start": 0, "run_end": 1},
        {"policy": "once_before_run", "run_start": True, "run_end": 1},
        {"policy": "once_before_run", "run_start": 0, "run_end": float("inf")},
        {"policy": "once_before_run", "run_start": 1, "run_end": 1},
        {
            "policy": "each_window",
            "run_start": 0,
            "run_end": 1,
            "window_start": None,
            "window_end": None,
        },
        {
            "policy": "each_window",
            "run_start": 0,
            "run_end": 1,
            "window_start": 0.5,
            "window_end": 0.5,
        },
        {
            "policy": "once_after_run",
            "run_start": 0,
            "run_end": 1,
            "window_start": 0,
            "window_end": 1,
        },
    ],
)
def test_execution_context_rejects_invalid_construction(kwargs) -> None:
    with pytest.raises((TypeError, ValueError)):
        biosim.ExecutionContext(**kwargs)


class SourceOperation(biosim.BioModule):
    execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

    def __init__(self, value: float = 2.0) -> None:
        self.value = value
        self.calls = 0

    def outputs(self):
        return {"value": SCALAR}

    def execute(self, inputs, *, context):
        self.calls += 1
        return {"value": self.value}


class MultiplyOperation(biosim.BioModule):
    execution_policy = "once_before_run"

    def __init__(self, factor: float = 2.0) -> None:
        self.factor = factor
        self.calls = 0

    def inputs(self):
        return {"value": SCALAR}

    def outputs(self):
        return {"value": SCALAR}

    def execute(self, inputs, *, context):
        self.calls += 1
        return {"value": float(inputs["value"].value) * self.factor}


def test_canonical_advance_window_requires_bioworld() -> None:
    module = SourceOperation()
    with pytest.raises(RuntimeError, match="must be invoked through BioWorld"):
        module.advance_window(1.0, 2.0)
    assert module.get_outputs() == {}


def test_canonical_get_outputs_updates_only_after_bioworld_commit() -> None:
    module = SourceOperation(4.0)
    context = biosim.ExecutionContext(
        policy=biosim.ExecutionPolicy.ONCE_BEFORE_RUN,
        run_start=0.0,
        run_end=0.1,
    )

    assert module.execute({}, context=context) == {"value": 4.0}
    assert module.get_outputs() == {}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", module)
    world.run(duration=0.1)

    output = module.get_outputs()["value"]
    assert output.value == 4.0
    assert output.source == "source"
    assert output.emitted_at == 0.0

    module.reset()
    assert module.get_outputs() == {}


def test_execute_adapter_works_through_signal_emitter_base() -> None:
    class EmitterOperation(biosim.SignalEmitterBioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def outputs(self):
            return {"value": SCALAR}

        def execute(self, inputs, *, context):
            return {"value": 9.0}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("emitter", EmitterOperation())
    world.run(duration=0.1)

    assert world.get_outputs("emitter")["value"].value == 9.0


def test_once_before_chain_drains_without_settle() -> None:
    source = SourceOperation()
    middle = MultiplyOperation(3.0)
    end = MultiplyOperation(5.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.add_biomodule("middle", middle)
    world.add_biomodule("end", end)
    world.connect("source.value", "middle.value")
    world.connect("middle.value", "end.value")

    world.run(duration=0.3)

    assert source.calls == middle.calls == end.calls == 1
    assert world.get_outputs("end")["value"].value == 30.0
    assert world.get_outputs("source")["value"].emitted_at == 0.0
    assert world.get_outputs("end")["value"].emitted_at == 0.0


def test_once_before_fan_in_waits_for_every_connected_input() -> None:
    class Add(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def inputs(self):
            return {"left": SCALAR, "right": SCALAR}

        def outputs(self):
            return {"total": SCALAR}

        def execute(self, inputs, *, context):
            return {"total": inputs["left"].value + inputs["right"].value}

    left = SourceOperation(4.0)
    right = SourceOperation(7.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("left", left)
    world.add_biomodule("right", right)
    world.add_biomodule("add", Add())
    world.connect("left.value", "add.left")
    world.connect("right.value", "add.right")

    world.run(duration=0.1)

    assert world.get_outputs("add")["total"].value == 11.0


def test_once_before_fan_out_and_independent_roots_are_deterministic() -> None:
    order: list[str] = []

    class TrackedSource(SourceOperation):
        def __init__(self, name, value):
            super().__init__(value)
            self.name = name

        def execute(self, inputs, *, context):
            order.append(self.name)
            return super().execute(inputs, context=context)

    class TrackedMultiply(MultiplyOperation):
        def __init__(self, name, factor):
            super().__init__(factor)
            self.name = name

        def execute(self, inputs, *, context):
            order.append(self.name)
            return super().execute(inputs, context=context)

    source = TrackedSource("source", 3.0)
    independent = TrackedSource("independent", 7.0)
    left = TrackedMultiply("left", 2.0)
    right = TrackedMultiply("right", 4.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.add_biomodule("independent", independent)
    world.add_biomodule("left", left)
    world.add_biomodule("right", right)
    world.connect("source.value", "left.value")
    world.connect("source.value", "right.value")

    world.run(duration=0.1)

    assert order == ["source", "independent", "left", "right"]
    assert world.get_outputs("left")["value"].value == 6.0
    assert world.get_outputs("right")["value"].value == 12.0


def test_once_after_receives_final_temporal_output() -> None:
    class Counter(biosim.BioModule):
        def __init__(self):
            self.count = 0
            self.current = {}

        def outputs(self):
            return {"value": SCALAR}

        def advance_window(self, start, end):
            self.count += 1
            self.current = {
                "value": biosim.ScalarSignal("counter", "value", self.count, end, spec=SCALAR)
            }

        def get_outputs(self):
            return self.current

    class Summary(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_AFTER_RUN

        def __init__(self):
            self.calls = 0

        def inputs(self):
            return {"value": SCALAR}

        def outputs(self):
            return {"summary": SCALAR}

        def execute(self, inputs, *, context):
            self.calls += 1
            return {"summary": inputs["value"].value * 10}

    summary = Summary()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("counter", Counter())
    world.add_biomodule("summary", summary)
    world.connect("counter.value", "summary.value")

    world.run(duration=0.3)

    assert summary.calls == 1
    assert world.get_outputs("summary")["summary"].value == 30
    assert world.get_outputs("summary")["summary"].emitted_at == pytest.approx(0.3)


def test_execute_each_window_runs_only_for_positive_windows() -> None:
    class WindowOperation(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

        def __init__(self):
            self.calls = 0

        def outputs(self):
            return {"value": SCALAR}

        def execute(self, inputs, *, context):
            self.calls += 1
            return {"value": self.calls}

    module = WindowOperation()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("operation", module)

    world.run(duration=0.3)
    world.settle(5)

    assert module.calls == 3
    assert world.get_outputs("operation")["value"].emitted_at == pytest.approx(0.3)


def test_canonical_modules_receive_complete_phase_contexts() -> None:
    contexts = []

    class Before(SourceOperation):
        def execute(self, inputs, *, context):
            contexts.append(context)
            return super().execute(inputs, context=context)

    class Window(SourceOperation):
        execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

        def execute(self, inputs, *, context):
            contexts.append(context)
            return super().execute(inputs, context=context)

    class After(SourceOperation):
        execution_policy = biosim.ExecutionPolicy.ONCE_AFTER_RUN

        def execute(self, inputs, *, context):
            contexts.append(context)
            return super().execute(inputs, context=context)

    world = biosim.BioWorld(communication_step=0.2)
    world.add_biomodule("before", Before())
    world.add_biomodule("window", Window())
    world.add_biomodule("after", After())
    world.run(duration=0.5)

    assert [context.policy for context in contexts] == [
        biosim.ExecutionPolicy.ONCE_BEFORE_RUN,
        biosim.ExecutionPolicy.EACH_WINDOW,
        biosim.ExecutionPolicy.EACH_WINDOW,
        biosim.ExecutionPolicy.EACH_WINDOW,
        biosim.ExecutionPolicy.ONCE_AFTER_RUN,
    ]
    assert contexts[0].run_start == 0.0
    assert contexts[0].run_end == 0.5
    assert (contexts[1].window_start, contexts[1].window_end) == (0.0, 0.2)
    assert (contexts[3].window_start, contexts[3].window_end) == pytest.approx((0.4, 0.5))
    assert contexts[-1].simulated_time == 0.5


def test_typed_canonical_output_is_rebound_and_retimestamped() -> None:
    class Typed(SourceOperation):
        def execute(self, inputs, *, context):
            return {
                "value": biosim.ScalarSignal(
                    source="caller",
                    name="different",
                    value=7.0,
                    emitted_at=99.0,
                    spec=SCALAR,
                )
            }

    module = Typed()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("typed", module)
    world.run(duration=0.1)

    output = world.get_outputs("typed")["value"]
    assert output.source == "typed"
    assert output.name == "value"
    assert output.value == 7.0
    assert output.emitted_at == 0.0


def test_once_policy_repeats_for_each_public_run_call() -> None:
    module = SourceOperation()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", module)

    world.run(duration=0.1)
    first = world.get_outputs("source")["value"]
    world.run(duration=0.1)
    second = world.get_outputs("source")["value"]

    assert module.calls == 2
    assert first.emitted_at == 0.0
    assert second.emitted_at == pytest.approx(0.1)


def test_repeated_run_chain_waits_for_current_run_upstream_output() -> None:
    source = SourceOperation(2.0)
    downstream = MultiplyOperation(3.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.add_biomodule("downstream", downstream)
    world.connect("source.value", "downstream.value")

    world.run(duration=0.1)
    source.value = 5.0
    world.run(duration=0.1)

    assert source.calls == downstream.calls == 2
    assert world.get_outputs("downstream")["value"].value == 15.0
    assert world.get_outputs("downstream")["value"].emitted_at == pytest.approx(0.1)


def test_missing_connected_input_fails_with_edge_details() -> None:
    class Empty(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def outputs(self):
            return {"value": SCALAR}

        def execute(self, inputs, *, context):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("empty", Empty())
    world.add_biomodule("consumer", MultiplyOperation())
    world.connect("empty.value", "consumer.value")

    with pytest.raises(RuntimeError, match=r"empty\.value->consumer\.value"):
        world.run(duration=0.1)


def test_optional_connected_input_does_not_block_execution() -> None:
    optional = biosim.SignalSpec.scalar(dtype="float64", required=False)

    class Empty(SourceOperation):
        def execute(self, inputs, *, context):
            self.calls += 1
            return {}

    class Consumer(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def inputs(self):
            return {"value": optional}

        def outputs(self):
            return {"value": SCALAR}

        def execute(self, inputs, *, context):
            return {"value": 9.0 if "value" not in inputs else inputs["value"].value}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("empty", Empty())
    world.add_biomodule("consumer", Consumer())
    world.connect("empty.value", "consumer.value")
    world.run(duration=0.1)

    assert world.get_outputs("consumer")["value"].value == 9.0


def test_invalid_execution_contracts_are_rejected() -> None:
    class Missing(biosim.BioModule):
        pass

    class Ambiguous(biosim.BioModule):
        def execute(self, inputs, *, context):
            return {}

        def advance_window(self, start, end):
            return

    class LegacyOnce(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def advance_window(self, start, end):
            return

    class Unknown(SourceOperation):
        execution_policy = "sometimes"

    class OneArgument(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def execute(self, inputs):
            return {}

    class PositionalContext(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def execute(self, inputs, context):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    with pytest.raises(TypeError, match=r"execute\(\) or advance_window\(\)"):
        world.add_biomodule("missing", Missing())
    with pytest.raises(TypeError, match="overrides both"):
        world.add_biomodule("ambiguous", Ambiguous())
    with pytest.raises(TypeError, match=r"must implement execute\(\)"):
        world.add_biomodule("legacy_once", LegacyOnce())
    with pytest.raises(ValueError, match="execution_policy"):
        world.add_biomodule("unknown", Unknown())
    with pytest.raises(TypeError, match=r"execute\(self, inputs, \*, context\)"):
        world.add_biomodule("one_argument", OneArgument())
    with pytest.raises(TypeError, match=r"execute\(self, inputs, \*, context\)"):
        world.add_biomodule("positional_context", PositionalContext())


def test_implicit_each_window_policy_warns_but_remains_supported() -> None:
    class Implicit(biosim.BioModule):
        def outputs(self):
            return {"value": SCALAR}

        def execute(self, inputs, *, context):
            return {"value": context.simulated_time}

    world = biosim.BioWorld(communication_step=0.1)
    with pytest.warns(RuntimeWarning, match="declare the policy explicitly"):
        world.add_biomodule("implicit", Implicit())
    world.run(duration=0.2)
    assert world.get_outputs("implicit")["value"].value == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (["not", "a", "mapping"], TypeError),
        ({"undeclared": 1.0}, KeyError),
        ({"value": [1.0, 2.0]}, TypeError),
    ],
)
def test_invalid_execute_outputs_fail_before_commit(result, error) -> None:
    class Invalid(SourceOperation):
        def execute(self, inputs, *, context):
            return result

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("invalid", Invalid())

    with pytest.raises(error):
        world.run(duration=0.1)
    assert world.get_outputs("invalid") == {}


def test_invalid_output_prevents_entire_once_layer_commit() -> None:
    class Invalid(SourceOperation):
        def execute(self, inputs, *, context):
            return {"undeclared": 1.0}

    valid = SourceOperation(4.0)
    invalid = Invalid()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("valid", valid)
    world.add_biomodule("invalid", invalid)

    with pytest.raises(KeyError, match="undeclared"):
        world.run(duration=0.1)

    assert world.get_outputs("valid") == {}
    assert valid.get_outputs() == {}
    assert world.snapshot()["completed_once"] == []


def test_phase_direction_and_once_cycles_are_rejected_before_execution() -> None:
    after = SourceOperation()
    after.execution_policy = biosim.ExecutionPolicy.ONCE_AFTER_RUN
    before = MultiplyOperation()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("after", after)
    world.add_biomodule("before", before)
    world.connect("after.value", "before.value")

    with pytest.raises(ValueError, match="invalid execution phase edge"):
        world.run(duration=0.1)

    left = MultiplyOperation()
    right = MultiplyOperation()
    cyclic = biosim.BioWorld(communication_step=0.1)
    cyclic.add_biomodule("left", left)
    cyclic.add_biomodule("right", right)
    cyclic.connect("left.value", "right.value")
    cyclic.connect("right.value", "left.value")
    with pytest.raises(ValueError, match="dependency cycle"):
        cyclic.run(duration=0.1)


def test_snapshot_restore_rehydrates_execute_outputs_and_completion_state() -> None:
    source = SourceOperation(8.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.run(duration=0.1)
    snapshot = world.snapshot()

    source._execution_outputs = {}
    world.restore(snapshot)

    assert snapshot["completed_once"] == ["source"]
    assert source.get_outputs()["value"].value == 8.0
    assert world.get_outputs("source")["value"].emitted_at == 0.0


def test_snapshot_before_once_execution_restores_without_uncommitted_output() -> None:
    source = SourceOperation(8.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.setup()
    before = world.snapshot()

    world.run(duration=0.1)
    world.restore(before)

    assert before["completed_once"] == []
    assert source.get_outputs() == {}
    assert world.get_outputs("source") == {}


def test_legacy_snapshot_without_completion_metadata_restores() -> None:
    source = SourceOperation(6.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.run(duration=0.1)
    snapshot = world.snapshot()
    snapshot.pop("completed_once")

    world.restore(snapshot)

    assert world.get_outputs("source")["value"].value == 6.0


def test_once_failure_is_retryable_on_next_run() -> None:
    class Flaky(SourceOperation):
        def execute(self, inputs, *, context):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary failure")
            return {"value": self.value}

    module = Flaky()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("flaky", module)

    with pytest.raises(RuntimeError, match="temporary failure"):
        world.run(duration=0.1)
    world.run(duration=0.1)

    assert module.calls == 2
    assert world.get_outputs("flaky")["value"].value == 2.0


def test_after_run_is_skipped_when_window_execution_fails() -> None:
    class FailingWindow(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

        def execute(self, inputs, *, context):
            raise RuntimeError("window failed")

    after = SourceOperation()
    after.execution_policy = biosim.ExecutionPolicy.ONCE_AFTER_RUN
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("window", FailingWindow())
    world.add_biomodule("after", after)

    with pytest.raises(RuntimeError, match="window failed"):
        world.run(duration=0.1)

    assert after.calls == 0
    assert world.get_outputs("after") == {}


def test_failed_repeat_run_does_not_expose_prior_once_output() -> None:
    class FailsSecondRun(SourceOperation):
        def execute(self, inputs, *, context):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("second run failed")
            return {"value": self.value}

    module = FailsSecondRun(4.0)
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", module)
    world.run(duration=0.1)
    assert world.get_outputs("source")["value"].value == 4.0

    with pytest.raises(RuntimeError, match="second run failed"):
        world.run(duration=0.1)

    assert module.get_outputs() == {}
    assert world.get_outputs("source") == {}


@pytest.mark.parametrize(
    "policy",
    [
        biosim.ExecutionPolicy.ONCE_BEFORE_RUN,
        biosim.ExecutionPolicy.EACH_WINDOW,
        biosim.ExecutionPolicy.ONCE_AFTER_RUN,
    ],
)
def test_cancellation_reaches_active_canonical_operation(policy) -> None:
    started = threading.Event()
    released = threading.Event()

    class Blocking(SourceOperation):
        execution_policy = policy

        def __init__(self):
            super().__init__()
            self.stop_received = False

        def execute(self, inputs, *, context):
            started.set()
            assert released.wait(timeout=2.0)
            self.calls += 1
            return {"value": self.value}

        def request_stop(self):
            self.stop_received = True
            released.set()

    module = Blocking()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("blocking", module)
    events = []
    world.on(lambda event, payload: events.append(event))
    thread = threading.Thread(target=world.run, kwargs={"duration": 0.1})
    thread.start()
    assert started.wait(timeout=2.0)

    world.request_stop()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert module.stop_received
    assert biosim.WorldEvent.STOPPED in events
    assert module.get_outputs() == {}
    assert world.get_outputs("blocking") == {}


def test_zero_duration_is_setup_only() -> None:
    module = SourceOperation()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", module)

    world.run(duration=0)

    assert module.calls == 0
    assert module.get_outputs() == {}
    assert world.get_outputs("source") == {}


def test_once_event_is_not_retimestamped_or_redelivered() -> None:
    event_spec = biosim.SignalSpec.event(schema={"value": "int"})

    class EventSource(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.ONCE_BEFORE_RUN

        def outputs(self):
            return {"event": event_spec}

        def execute(self, inputs, *, context):
            return {"event": {"value": 1}}

    class EventConsumer(biosim.BioModule):
        def __init__(self):
            self.deliveries = 0

        def inputs(self):
            return {"event": event_spec}

        def set_inputs(self, signals):
            if "event" in signals:
                self.deliveries += 1

        def advance_window(self, start, end):
            return

    source = EventSource()
    consumer = EventConsumer()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("source", source)
    world.add_biomodule("consumer", consumer)
    world.connect("source.event", "consumer.event")
    world.run(duration=0.3)

    assert consumer.deliveries == 1
    assert world.get_outputs("source")["event"].emitted_at == 0.0

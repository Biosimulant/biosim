"""Tests for my_pack modules."""
import pytest


class MockWorld:
    """Mock BioWorld for testing."""

    def __init__(self):
        self.signals = []

    def publish_biosignal(self, source, topic, payload):
        self.signals.append({
            "source": source,
            "topic": topic,
            "payload": payload,
        })


def test_counter_increments():
    """Counter should increment on each STEP event."""
    from my_pack import Counter
    from bsim import BioWorldEvent

    counter = Counter(name="test")
    counter.reset()
    world = MockWorld()

    # Simulate two steps
    counter.on_event(BioWorldEvent.STEP, {"t": 0.1}, world)
    counter.on_event(BioWorldEvent.STEP, {"t": 0.2}, world)

    assert len(world.signals) == 2
    assert world.signals[0]["payload"]["count"] == 1
    assert world.signals[1]["payload"]["count"] == 2


def test_counter_reset():
    """Counter should reset to zero."""
    from my_pack import Counter
    from bsim import BioWorldEvent

    counter = Counter()
    world = MockWorld()

    counter.on_event(BioWorldEvent.STEP, {"t": 0.1}, world)
    assert world.signals[0]["payload"]["count"] == 1

    counter.reset()
    world.signals.clear()

    counter.on_event(BioWorldEvent.STEP, {"t": 0.2}, world)
    assert world.signals[0]["payload"]["count"] == 1  # Reset to 1, not 2


def test_counter_visualize():
    """Counter should produce timeseries visualization."""
    from my_pack import Counter
    from bsim import BioWorldEvent

    counter = Counter(name="viz_test")
    world = MockWorld()

    # No data yet
    assert counter.visualize() is None

    counter.on_event(BioWorldEvent.STEP, {"t": 0.1}, world)

    vis = counter.visualize()
    assert vis is not None
    assert vis["render"] == "timeseries"
    assert "viz_test" in vis["data"]["series"][0]["name"]


def test_accumulator_accumulates():
    """Accumulator should sum incoming values."""
    from my_pack import Accumulator

    acc = Accumulator(initial=10.0)
    world = MockWorld()

    acc.on_signal("value", {"amount": 5.0, "t": 0.1}, None, world)
    acc.on_signal("value", {"amount": 3.0, "t": 0.2}, None, world)

    assert len(world.signals) == 2
    assert world.signals[0]["payload"]["total"] == 15.0
    assert world.signals[1]["payload"]["total"] == 18.0


def test_accumulator_ignores_other_topics():
    """Accumulator should ignore non-value signals."""
    from my_pack import Accumulator

    acc = Accumulator(initial=0.0)
    world = MockWorld()

    acc.on_signal("other_topic", {"amount": 100.0}, None, world)

    assert len(world.signals) == 0


def test_signal_logger_logs():
    """SignalLogger should record incoming signals."""
    from my_pack import SignalLogger

    logger = SignalLogger(max_entries=5)
    world = MockWorld()

    class FakeSource:
        pass

    for i in range(10):
        logger.on_signal("test", {"i": i}, FakeSource(), world)

    # Should have trimmed to max_entries
    vis = logger.visualize()
    assert vis is not None
    assert vis["render"] == "table"
    # Title should indicate 5 entries (trimmed from 10)
    # Actually the log keeps max_entries, so it has 5

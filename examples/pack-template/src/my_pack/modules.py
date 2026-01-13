"""Custom BioModule implementations.

These modules can be referenced in YAML configs:
    modules:
      counter:
        class: my_pack.Counter
        args:
          name: "step_counter"
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from bsim import BioWorld, BioWorldEvent

from bsim import BioModule


class Counter(BioModule):
    """Counts simulation steps and emits the count.

    Outputs:
        count: {"count": int, "t": float}

    Parameters:
        name: Display name for this counter
    """

    def __init__(self, name: str = "counter") -> None:
        self.name = name
        self._count = 0
        self._history: List[List[float]] = []

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return set()

    def outputs(self) -> Set[str]:
        return {"count"}

    def reset(self) -> None:
        self._count = 0
        self._history = []

    def on_event(
        self,
        event: "BioWorldEvent",
        payload: Dict[str, Any],
        world: "BioWorld",
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        self._count += 1
        t = payload.get("t", 0.0)
        self._history.append([t, self._count])

        world.publish_biosignal(
            self,
            topic="count",
            payload={"count": self._count, "t": t}
        )

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        pass  # Counter doesn't receive signals

    def visualize(self) -> Optional[Dict[str, Any]]:
        if not self._history:
            return None
        return {
            "render": "timeseries",
            "data": {
                "series": [{"name": self.name, "points": self._history}],
                "title": f"Counter: {self.name}",
            },
        }


class Accumulator(BioModule):
    """Receives values and accumulates them over time.

    Inputs:
        value: {"amount": float} - adds amount to total

    Outputs:
        total: {"total": float, "t": float}

    Parameters:
        initial: Starting value for accumulator
    """

    def __init__(self, initial: float = 0.0) -> None:
        self._initial = initial
        self._total = initial
        self._history: List[List[float]] = []

    def inputs(self) -> Set[str]:
        return {"value"}

    def outputs(self) -> Set[str]:
        return {"total"}

    def reset(self) -> None:
        self._total = self._initial
        self._history = []

    def on_event(
        self,
        event: "BioWorldEvent",
        payload: Dict[str, Any],
        world: "BioWorld",
    ) -> None:
        pass  # Accumulator is signal-driven, not event-driven

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "value":
            return

        amount = payload.get("amount", 0.0)
        self._total += amount
        t = payload.get("t", 0.0)
        self._history.append([t, self._total])

        world.publish_biosignal(
            self,
            topic="total",
            payload={"total": self._total, "t": t}
        )

    def visualize(self) -> Optional[Dict[str, Any]]:
        if not self._history:
            return None
        return {
            "render": "timeseries",
            "data": {
                "series": [{"name": "total", "points": self._history}],
                "title": "Accumulator",
            },
        }


class SignalLogger(BioModule):
    """Logs all incoming signals for debugging.

    Inputs:
        any_signal: Accepts any signal topic

    Parameters:
        max_entries: Maximum log entries to keep
    """

    def __init__(self, max_entries: int = 100) -> None:
        self.max_entries = max_entries
        self._log: List[Dict[str, Any]] = []

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()  # Don't subscribe to world events

    def inputs(self) -> Set[str]:
        return set()  # Accept any signal (empty = permissive)

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        self._log = []

    def on_event(
        self,
        event: "BioWorldEvent",
        payload: Dict[str, Any],
        world: "BioWorld",
    ) -> None:
        pass

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        entry = {
            "topic": topic,
            "payload": payload,
            "source": source.__class__.__name__ if source else "unknown",
        }
        self._log.append(entry)

        # Trim to max entries
        if len(self._log) > self.max_entries:
            self._log = self._log[-self.max_entries:]

    def visualize(self) -> Optional[Dict[str, Any]]:
        if not self._log:
            return None

        # Show last 10 entries as table
        recent = self._log[-10:]
        rows = [
            [e["source"], e["topic"], str(e["payload"])[:50]]
            for e in recent
        ]

        return {
            "render": "table",
            "data": {
                "columns": ["Source", "Topic", "Payload"],
                "rows": rows,
                "title": f"Signal Log ({len(self._log)} entries)",
            },
        }

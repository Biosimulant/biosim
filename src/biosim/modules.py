from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

from .signals import BioSignal, SignalSpec, make_signal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .visuals import VisualSpec


class BioModule(ABC):
    """Runnable module interface for the communication-step kernel."""

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the module for a run."""
        return

    def reset(self) -> None:
        """Reset the module to its initial state."""
        return

    def set_inputs(self, signals: Dict[str, BioSignal]) -> None:
        """Receive committed inputs for the current communication window."""
        return

    @abstractmethod
    def advance_window(self, start: float, end: float) -> None:
        """Advance internal state across one communication window."""
        raise NotImplementedError  # pragma: no cover - abstract

    @abstractmethod
    def get_outputs(self) -> Dict[str, BioSignal]:
        """Return current output signals for atomic boundary commit."""
        raise NotImplementedError  # pragma: no cover - abstract

    def inputs(self) -> Mapping[str, SignalSpec]:
        """Declared input port specifications."""
        return {}

    def outputs(self) -> Mapping[str, SignalSpec]:
        """Declared output port specifications."""
        return {}

    def snapshot(self) -> Dict[str, Any]:
        """Return serializable module state for branching/restoration."""
        return {}

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Restore module state from a prior snapshot."""
        return

    def visualize(self) -> Optional["VisualSpec" | List["VisualSpec"]]:
        return None


class SignalEmitterBioModule(BioModule):
    """Optional BioModule base for modules that publish typed output signals.

    This class intentionally does not change ``BioModule``. It only centralizes
    the common ``_outputs`` storage and value-to-signal wrapping pattern for
    modules that want it.
    """

    def __init__(self) -> None:
        self._outputs: Dict[str, BioSignal] = {}

    def source_name(self) -> str:
        """Return the source name used for emitted signals."""

        return str(getattr(self, "_world_name", self.__class__.__name__))

    def emit_signal(
        self,
        name: str,
        value: Any,
        emitted_at: float,
        *,
        spec: SignalSpec | Mapping[str, Any] | None = None,
    ) -> BioSignal:
        """Build one typed output signal for a declared output port."""

        if spec is None:
            spec = self.outputs().get(name)
        return make_signal(
            spec,
            source=self.source_name(),
            name=name,
            value=value,
            emitted_at=float(emitted_at),
        )

    def output_payload(self, t: float) -> Mapping[str, Any]:
        """Return raw output values keyed by output port.

        Subclasses can override this and call ``publish_outputs()`` from their
        lifecycle code.
        """

        return {}

    def publish_outputs(self, t: float, payloads: Mapping[str, Any] | None = None) -> None:
        """Wrap raw output payloads into typed BioSignals."""

        payloads = self.output_payload(t) if payloads is None else payloads
        specs = self.outputs()
        self._outputs = {
            name: self.emit_signal(name, value, float(t), spec=specs.get(name))
            for name, value in payloads.items()
        }

    def get_outputs(self) -> Dict[str, BioSignal]:
        """Return current output signals for atomic boundary commit."""

        return dict(getattr(self, "_outputs", {}))

    def clear_outputs(self) -> None:
        self._outputs = {}


class StatefulBioModule(SignalEmitterBioModule):
    """Optional base for fixed-step stateful modules.

    Subclasses provide the domain behavior through hooks. Modules with unusual
    timing or solver requirements should continue inheriting directly from
    ``BioModule`` or ``SignalEmitterBioModule``.
    """

    def __init__(
        self,
        *,
        integration_step: float = 1.0,
        max_history_points: int = 10000,
        record_initial_state: bool = False,
        publish_on_setup: bool = False,
        publish_on_zero_window: bool = True,
    ) -> None:
        super().__init__()
        if integration_step <= 0:
            raise ValueError("integration_step must be positive")
        if max_history_points <= 0:
            raise ValueError("max_history_points must be positive")
        self.integration_step = float(integration_step)
        self.max_history_points = int(max_history_points)
        self.record_initial_state = bool(record_initial_state)
        self.publish_on_setup = bool(publish_on_setup)
        self.publish_on_zero_window = bool(publish_on_zero_window)
        self._time = 0.0
        self._input_overrides: Dict[str, BioSignal] = {}
        self._history: List[Any] = []

    @property
    def history(self) -> List[Any]:
        return list(getattr(self, "_history", []))

    def reset_state(self) -> None:
        """Reset subclass-owned state."""

        return

    def apply_overrides(self, *, reset_initial_state: bool) -> None:
        """Apply currently stored input overrides to subclass state."""

        return

    def step(self, h: float) -> None:
        """Advance subclass state by one internal step."""

        return

    def record_state(self, t: float) -> None:
        """Record subclass state at time ``t``."""

        return

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.reset()
        if self.publish_on_setup:
            self.publish_outputs(self._time)

    def reset(self) -> None:
        self._time = 0.0
        self._input_overrides = {}
        self._history = []
        self.clear_outputs()
        self.reset_state()

    def set_inputs(self, signals: Dict[str, BioSignal]) -> None:
        self._input_overrides = dict(signals or {})
        self.apply_overrides(reset_initial_state=self._time <= 0.0 and not self._history)

    def advance_window(
        self,
        start: float | None = None,
        end: float | None = None,
        inputs: Dict[str, BioSignal] | None = None,
    ) -> Dict[str, BioSignal]:
        if inputs is not None:
            self.set_inputs(inputs)
        else:
            self.apply_overrides(reset_initial_state=False)

        if self.record_initial_state and not self._history:
            self.record_state(self._time)
            self.trim_history()

        if end is None:
            end = self._time + float(getattr(self, "communication_step", self.integration_step) or self.integration_step)
        target = float(end)
        if target <= self._time:
            if self.publish_on_zero_window:
                self.publish_outputs(self._time)
            return self.get_outputs()

        current = self._time
        while current < target - 1e-12:
            h = min(self.integration_step, target - current)
            self.step(h)
            current += h
            self._time = current
            self.record_state(current)
            self.trim_history()

        self.publish_outputs(self._time)
        return self.get_outputs()

    def trim_history(self) -> None:
        history = getattr(self, "_history", None)
        if isinstance(history, list) and len(history) > self.max_history_points:
            del history[:-self.max_history_points]

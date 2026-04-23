from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

from .signals import BioSignal, SignalSpec

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .visuals import VisualSpec


class BioModule(ABC):
    """Runnable module interface for the 1.5 communication-step kernel."""

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

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from .signals import BioSignal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .visuals import VisualSpec


class BioModule(ABC):
    """Runnable module interface for the BioWorld orchestrator."""

    # Minimum time step for this module (in BioWorld's canonical time unit).
    min_dt: float = 0.0

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the module for a run. Default is a no-op."""
        return

    def reset(self) -> None:
        """Reset the module to its initial state. Default is a no-op."""
        return

    @abstractmethod
    def advance_to(self, t: float) -> None:
        """Advance the module's internal state to time t."""
        raise NotImplementedError

    def set_inputs(self, signals: Dict[str, BioSignal]) -> None:
        """Receive input signals for the next advance step."""
        return

    @abstractmethod
    def get_outputs(self) -> Dict[str, BioSignal]:
        """Return current output signals."""
        raise NotImplementedError

    def get_state(self) -> Dict[str, Any]:
        """Return serializable state for checkpointing."""
        return {}

    def next_due_time(self, now: float) -> float:
        """Return the next time this module should be stepped."""
        return now + self.min_dt

    # --- Optional Port Metadata (for validation and tooling) ---
    # Return declared input and output port names. Defaults are empty, meaning
    # permissive (no validation). If non-empty, the wiring builder/loader will
    # validate connections against these sets.
    def inputs(self) -> Set[str]:
        return set()

    def outputs(self) -> Set[str]:
        return set()

    # Optional schema maps: port name -> schema/type object. If both source and
    # destination declare schemas for a connected port, simple equality checks
    # can be applied by tooling in the future. Currently unused.
    def input_schemas(self) -> Dict[str, Any]:
        return {}

    def output_schemas(self) -> Dict[str, Any]:
        return {}

    # --- Optional: visualization ---
    # Modules can optionally expose a web-native visualization spec to be
    # rendered by a browser client. Return either a single dict or a list of
    # dicts with the fixed shape: {"render": <type>, "data": <payload>}.
    # Default returns None (no visuals).
    def visualize(self) -> Optional["VisualSpec" | List["VisualSpec"]]:
        return None

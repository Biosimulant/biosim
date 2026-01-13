"""
TimeBroker - Synchronization layer for multi-adapter simulations.

The TimeBroker coordinates time advancement across multiple adapters that may
operate at different time scales. It handles:

1. Time unit conversion (e.g., ms for NeuroML, seconds for SBML)
2. Synchronization points for signal exchange
3. Adaptive stepping based on adapter requirements
4. Checkpointing and rollback

Example:
    broker = TimeBroker()
    broker.register("metabolism", sbml_adapter, time_scale="seconds")
    broker.register("neurons", neuroml_adapter, time_scale="ms")
    broker.add_connection("metabolism.ATP", "neurons.energy_input")

    for t in broker.run(duration=10.0, dt=0.001):
        # Adapters are synchronized at each step
        signals = broker.get_all_signals()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Callable, Protocol
from enum import Enum
import heapq

from bsim.adapters.base import SimulatorAdapter
from bsim.adapters.signals import BioSignal


class TimeScale(Enum):
    """Common time scales used in biological models."""

    SECONDS = "seconds"
    MILLISECONDS = "ms"
    MICROSECONDS = "us"
    MINUTES = "min"
    HOURS = "hours"

    @property
    def to_seconds(self) -> float:
        """Conversion factor to seconds."""
        factors = {
            TimeScale.SECONDS: 1.0,
            TimeScale.MILLISECONDS: 0.001,
            TimeScale.MICROSECONDS: 1e-6,
            TimeScale.MINUTES: 60.0,
            TimeScale.HOURS: 3600.0,
        }
        return factors[self]


@dataclass
class AdapterEntry:
    """Entry for a registered adapter in the broker."""

    name: str
    adapter: SimulatorAdapter
    time_scale: TimeScale
    priority: int = 0  # Higher priority adapters run first
    min_dt: float = 0.0  # Minimum time step for this adapter
    last_time: float = 0.0  # Last synchronization time (in canonical units)


@dataclass
class Connection:
    """A signal connection between two adapters."""

    source_adapter: str
    source_signal: str
    target_adapter: str
    target_signal: str
    transform: Callable[[float], float] | None = None  # Optional transformation


@dataclass
class SyncEvent:
    """An event scheduled for synchronization."""

    time: float
    adapter_name: str
    event_type: str = "sync"

    def __lt__(self, other: SyncEvent) -> bool:
        return self.time < other.time


class TimeBroker:
    """
    Coordinates time advancement across multiple adapters.

    The TimeBroker manages synchronization between adapters running at
    different time scales. It maintains a canonical time (in seconds) and
    converts to each adapter's native time scale as needed.

    Key features:
    - Automatic time scale conversion
    - Signal routing between adapters
    - Adaptive stepping based on adapter requirements
    - Event scheduling for periodic synchronization
    - Checkpointing for rollback capability

    Example:
        >>> broker = TimeBroker()
        >>> broker.register("sbml_model", sbml_adapter, time_scale="seconds")
        >>> broker.register("neuro_model", neuro_adapter, time_scale="ms")
        >>> broker.connect("sbml_model.glucose", "neuro_model.energy")
        >>>
        >>> broker.setup()
        >>> for t in broker.run(duration=1.0, dt=0.001):
        ...     signals = broker.get_all_signals()
        ...     # Process signals...
    """

    def __init__(self, canonical_scale: TimeScale = TimeScale.SECONDS):
        """
        Initialize the TimeBroker.

        Args:
            canonical_scale: The canonical time scale for the broker.
                All times are converted to this scale internally.
        """
        self._canonical_scale = canonical_scale
        self._adapters: dict[str, AdapterEntry] = {}
        self._connections: list[Connection] = []
        self._current_time = 0.0  # Canonical time
        self._event_queue: list[SyncEvent] = []
        self._checkpoints: list[dict[str, Any]] = []
        self._is_setup = False

    def register(
        self,
        name: str,
        adapter: SimulatorAdapter,
        time_scale: str | TimeScale = TimeScale.SECONDS,
        priority: int = 0,
        min_dt: float = 0.0,
    ) -> None:
        """
        Register an adapter with the broker.

        Args:
            name: Unique identifier for the adapter.
            adapter: The simulator adapter instance.
            time_scale: Time scale used by the adapter.
            priority: Execution priority (higher runs first).
            min_dt: Minimum time step for this adapter (in adapter's scale).
        """
        if isinstance(time_scale, str):
            time_scale = TimeScale(time_scale)

        self._adapters[name] = AdapterEntry(
            name=name,
            adapter=adapter,
            time_scale=time_scale,
            priority=priority,
            min_dt=min_dt,
        )

    def connect(
        self,
        source: str,
        target: str,
        transform: Callable[[float], float] | None = None,
    ) -> None:
        """
        Connect a signal from one adapter to another.

        Args:
            source: Source signal in format "adapter_name.signal_name".
            target: Target signal in format "adapter_name.signal_name".
            transform: Optional function to transform the signal value.
        """
        source_parts = source.split(".", 1)
        target_parts = target.split(".", 1)

        if len(source_parts) != 2 or len(target_parts) != 2:
            raise ValueError(
                "Source and target must be in format 'adapter.signal'"
            )

        self._connections.append(
            Connection(
                source_adapter=source_parts[0],
                source_signal=source_parts[1],
                target_adapter=target_parts[0],
                target_signal=target_parts[1],
                transform=transform,
            )
        )

    def setup(self, config: dict[str, Any] | None = None) -> None:
        """
        Set up all registered adapters.

        Args:
            config: Optional configuration dictionary.
        """
        config = config or {}

        # Set up adapters in priority order
        sorted_adapters = sorted(
            self._adapters.values(),
            key=lambda a: -a.priority,
        )

        for entry in sorted_adapters:
            adapter_config = config.get(entry.name, {})
            entry.adapter.setup(adapter_config)

        self._is_setup = True
        self._current_time = 0.0

    def _to_canonical(self, time: float, scale: TimeScale) -> float:
        """Convert time from adapter scale to canonical scale."""
        # Convert to seconds first, then to canonical
        seconds = time * scale.to_seconds
        return seconds / self._canonical_scale.to_seconds

    def _from_canonical(self, time: float, scale: TimeScale) -> float:
        """Convert time from canonical scale to adapter scale."""
        # Convert from canonical to seconds, then to adapter scale
        seconds = time * self._canonical_scale.to_seconds
        return seconds / scale.to_seconds

    def _propagate_signals(self) -> None:
        """Propagate signals between connected adapters."""
        for conn in self._connections:
            # Get source signal
            source_entry = self._adapters.get(conn.source_adapter)
            if source_entry is None:
                continue

            outputs = source_entry.adapter.get_outputs()
            source_signal = outputs.get(conn.source_signal)

            if source_signal is None:
                continue

            # Transform if needed
            value = source_signal.value
            if conn.transform is not None:
                value = conn.transform(value)

            # Create target signal
            target_signal = BioSignal(
                source=conn.source_adapter,
                name=conn.target_signal,
                value=value,
                time=self._current_time,
                metadata=source_signal.metadata,
            )

            # Inject into target adapter
            target_entry = self._adapters.get(conn.target_adapter)
            if target_entry is not None:
                target_entry.adapter.set_input(conn.target_signal, target_signal)

    def step(self, dt: float) -> float:
        """
        Advance all adapters by dt (in canonical time).

        Args:
            dt: Time step in canonical units.

        Returns:
            The new current time.
        """
        if not self._is_setup:
            raise RuntimeError("Broker not set up. Call setup() first.")

        target_time = self._current_time + dt

        # Propagate signals before stepping
        self._propagate_signals()

        # Step each adapter
        sorted_adapters = sorted(
            self._adapters.values(),
            key=lambda a: -a.priority,
        )

        for entry in sorted_adapters:
            # Convert target time to adapter's scale
            adapter_time = self._from_canonical(target_time, entry.time_scale)

            # Check minimum dt requirement
            last_adapter_time = self._from_canonical(
                entry.last_time, entry.time_scale
            )
            if adapter_time - last_adapter_time < entry.min_dt:
                continue  # Skip if dt is too small

            # Advance the adapter
            entry.adapter.advance_to(adapter_time)
            entry.last_time = target_time

        self._current_time = target_time
        return self._current_time

    def run(
        self,
        duration: float,
        dt: float,
        callback: Callable[[float], None] | None = None,
    ) -> Iterator[float]:
        """
        Run the simulation for a given duration.

        Args:
            duration: Total simulation duration (in canonical units).
            dt: Time step (in canonical units).
            callback: Optional callback called at each step.

        Yields:
            Current time after each step.
        """
        if not self._is_setup:
            raise RuntimeError("Broker not set up. Call setup() first.")

        end_time = self._current_time + duration

        while self._current_time < end_time:
            # Calculate next step size
            remaining = end_time - self._current_time
            step_dt = min(dt, remaining)

            # Step
            self.step(step_dt)

            # Callback
            if callback is not None:
                callback(self._current_time)

            yield self._current_time

    def get_all_signals(self) -> dict[str, dict[str, BioSignal]]:
        """
        Get all output signals from all adapters.

        Returns:
            Nested dict: {adapter_name: {signal_name: BioSignal}}
        """
        result = {}
        for name, entry in self._adapters.items():
            result[name] = entry.adapter.get_outputs()
        return result

    def get_signal(self, path: str) -> BioSignal | None:
        """
        Get a specific signal by path.

        Args:
            path: Signal path in format "adapter_name.signal_name".

        Returns:
            The BioSignal or None if not found.
        """
        parts = path.split(".", 1)
        if len(parts) != 2:
            return None

        adapter_name, signal_name = parts
        entry = self._adapters.get(adapter_name)
        if entry is None:
            return None

        outputs = entry.adapter.get_outputs()
        return outputs.get(signal_name)

    def checkpoint(self) -> int:
        """
        Create a checkpoint of the current state.

        Returns:
            Checkpoint ID that can be used for rollback.
        """
        checkpoint = {
            "time": self._current_time,
            "adapters": {
                name: entry.adapter.get_state()
                for name, entry in self._adapters.items()
            },
        }
        self._checkpoints.append(checkpoint)
        return len(self._checkpoints) - 1

    def rollback(self, checkpoint_id: int) -> None:
        """
        Rollback to a previous checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to restore.
        """
        if checkpoint_id < 0 or checkpoint_id >= len(self._checkpoints):
            raise ValueError(f"Invalid checkpoint ID: {checkpoint_id}")

        checkpoint = self._checkpoints[checkpoint_id]
        self._current_time = checkpoint["time"]

        # Restore adapter states (if they support it)
        for name, state in checkpoint["adapters"].items():
            entry = self._adapters.get(name)
            if entry is not None and hasattr(entry.adapter, "set_state"):
                entry.adapter.set_state(state)
            entry.last_time = self._current_time

        # Clear checkpoints after rollback
        self._checkpoints = self._checkpoints[: checkpoint_id + 1]

    def reset(self) -> None:
        """Reset all adapters to initial conditions."""
        for entry in self._adapters.values():
            entry.adapter.reset()
            entry.last_time = 0.0
        self._current_time = 0.0
        self._checkpoints.clear()

    @property
    def current_time(self) -> float:
        """Current simulation time in canonical units."""
        return self._current_time

    @property
    def adapter_names(self) -> list[str]:
        """List of registered adapter names."""
        return list(self._adapters.keys())

    def get_adapter(self, name: str) -> SimulatorAdapter | None:
        """Get an adapter by name."""
        entry = self._adapters.get(name)
        return entry.adapter if entry else None


class AdaptiveTimeBroker(TimeBroker):
    """
    TimeBroker with adaptive time stepping.

    This broker automatically adjusts the time step based on
    signal change rates and adapter requirements.
    """

    def __init__(
        self,
        canonical_scale: TimeScale = TimeScale.SECONDS,
        min_dt: float = 1e-6,
        max_dt: float = 0.1,
        error_tolerance: float = 0.01,
    ):
        """
        Initialize the AdaptiveTimeBroker.

        Args:
            canonical_scale: Canonical time scale.
            min_dt: Minimum allowed time step.
            max_dt: Maximum allowed time step.
            error_tolerance: Target error tolerance for step size selection.
        """
        super().__init__(canonical_scale)
        self._min_dt = min_dt
        self._max_dt = max_dt
        self._error_tolerance = error_tolerance
        self._last_signals: dict[str, dict[str, float]] = {}
        self._current_dt = max_dt

    def _estimate_error(self) -> float:
        """Estimate error based on signal change rate."""
        current_signals = self.get_all_signals()
        max_change = 0.0

        for adapter_name, signals in current_signals.items():
            last = self._last_signals.get(adapter_name, {})
            for signal_name, signal in signals.items():
                last_value = last.get(signal_name, signal.value)
                if last_value != 0:
                    change = abs(signal.value - last_value) / abs(last_value)
                    max_change = max(max_change, change)

        return max_change

    def _update_dt(self) -> None:
        """Update the time step based on error estimate."""
        error = self._estimate_error()

        if error > self._error_tolerance:
            # Reduce dt
            self._current_dt = max(self._min_dt, self._current_dt * 0.5)
        elif error < self._error_tolerance * 0.1:
            # Increase dt
            self._current_dt = min(self._max_dt, self._current_dt * 1.5)

    def step(self, dt: float | None = None) -> float:
        """
        Advance with adaptive time stepping.

        Args:
            dt: Optional time step override. If None, uses adaptive dt.

        Returns:
            The new current time.
        """
        if dt is None:
            dt = self._current_dt

        result = super().step(dt)

        # Update stored signals and dt
        self._last_signals = {
            name: {
                sig_name: sig.value
                for sig_name, sig in signals.items()
            }
            for name, signals in self.get_all_signals().items()
        }
        self._update_dt()

        return result

    def run(
        self,
        duration: float,
        dt: float | None = None,
        callback: Callable[[float], None] | None = None,
    ) -> Iterator[float]:
        """
        Run with adaptive time stepping.

        Args:
            duration: Total simulation duration.
            dt: If provided, use fixed dt. Otherwise use adaptive.
            callback: Optional callback at each step.

        Yields:
            Current time after each step.
        """
        if not self._is_setup:
            raise RuntimeError("Broker not set up. Call setup() first.")

        end_time = self._current_time + duration
        use_adaptive = dt is None

        while self._current_time < end_time:
            remaining = end_time - self._current_time

            if use_adaptive:
                step_dt = min(self._current_dt, remaining)
            else:
                step_dt = min(dt, remaining)

            self.step(step_dt)

            if callback is not None:
                callback(self._current_time)

            yield self._current_time

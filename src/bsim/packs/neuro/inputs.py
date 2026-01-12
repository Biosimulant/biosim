# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Input modules for the neuro pack: spike generators and current injectors."""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent


class PoissonInput:
    """Generate spikes according to a Poisson process.

    Emits `spikes` topic with payload `{"t": float, "ids": [int, ...]}` on each STEP.

    Parameters:
        n: Number of independent spike sources (neuron indices 0..n-1).
        rate_hz: Firing rate in Hz for each source.
        seed: Optional random seed for reproducibility.
    """

    def __init__(self, n: int = 100, rate_hz: float = 10.0, seed: Optional[int] = None) -> None:
        self.n = n
        self.rate_hz = rate_hz
        self.seed = seed
        self._rng: random.Random = random.Random(seed)
        self._time: float = 0.0
        self._spike_counts: List[int] = []  # spike count per step for visualization
        self._spike_times: List[float] = []  # time points

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return set()

    def outputs(self) -> Set[str]:
        return {"spikes"}

    def reset(self) -> None:
        """Reset internal state for a new simulation run."""
        self._rng = random.Random(self.seed)
        self._time = 0.0
        self._spike_counts = []
        self._spike_times = []

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        # Get time and dt from payload
        t = float(payload.get("t", self._time))
        # dt is inferred from time difference (or assume small step)
        dt = t - self._time if t > self._time else 0.001
        self._time = t

        # For each neuron, probability of spike in interval dt
        # P(spike) = 1 - exp(-rate * dt) ~ rate * dt for small dt
        prob = self.rate_hz * dt
        spiked_ids: List[int] = []
        for i in range(self.n):
            if self._rng.random() < prob:
                spiked_ids.append(i)

        # Record for visualization
        self._spike_times.append(t)
        self._spike_counts.append(len(spiked_ids))

        # Always emit even if no spikes (empty list)
        world.publish_biosignal(self, topic="spikes", payload={"t": t, "ids": spiked_ids})

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        pass  # PoissonInput does not receive signals

    def visualize(self) -> Optional[Dict[str, Any]]:
        """Return a timeseries visualization of spike counts over time."""
        if not self._spike_times:
            return None
        points = list(zip(self._spike_times, self._spike_counts))
        return {
            "render": "timeseries",
            "data": {
                "series": [{"name": "spike_count", "points": points}],
                "title": f"PoissonInput (n={self.n}, rate={self.rate_hz}Hz)",
            },
            "description": (
                f"Poisson spike generator with {self.n} independent sources firing at {self.rate_hz}Hz. "
                "Shows number of spikes generated per timestep. Poisson processes model random, "
                "independent spike arrival typical of background synaptic input."
            ),
        }


# Register as BioModule via duck-typing (no inheritance needed, but let's be explicit)
from bsim import BioModule


class PoissonInput(PoissonInput, BioModule):  # type: ignore[no-redef]
    """PoissonInput as a proper BioModule."""
    pass


class StepCurrent:
    """Inject a constant or scheduled current.

    Emits `current` topic with payload `{"t": float, "I": float}` on each STEP.

    Parameters:
        I: Constant current amplitude (in nA or arbitrary units).
        schedule: Optional list of (start_t, end_t, I_value) tuples for time-varying current.
                  If provided, `I` is used as the default when outside scheduled intervals.
    """

    def __init__(
        self,
        I: float = 10.0,
        schedule: Optional[List[tuple]] = None,
    ) -> None:
        self.I_default = I
        self.schedule = schedule or []
        self._time: float = 0.0
        self._current_history: List[List[float]] = []  # [[t, I], ...]

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return set()

    def outputs(self) -> Set[str]:
        return {"current"}

    def reset(self) -> None:
        self._time = 0.0
        self._current_history = []

    def _get_current(self, t: float) -> float:
        """Get current value at time t based on schedule."""
        for start, end, I_val in self.schedule:
            if start <= t < end:
                return float(I_val)
        return self.I_default

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        t = float(payload.get("t", self._time))
        self._time = t

        I = self._get_current(t)
        self._current_history.append([t, I])
        world.publish_biosignal(self, topic="current", payload={"t": t, "I": I})

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        pass

    def visualize(self) -> Optional[Dict[str, Any]]:
        """Return a timeseries visualization of injected current over time."""
        if not self._current_history:
            return None
        return {
            "render": "timeseries",
            "data": {
                "series": [{"name": "I", "points": self._current_history}],
                "title": f"StepCurrent (I={self.I_default})",
            },
            "description": (
                f"Current injection with default amplitude {self.I_default} (arbitrary units). "
                "This current is directly added to the target neuron's membrane equation, "
                "driving it toward threshold and producing spikes when sufficiently strong."
            ),
        }


class StepCurrent(StepCurrent, BioModule):  # type: ignore[no-redef]
    """StepCurrent as a proper BioModule."""
    pass


# Alias for backward compatibility / alternative naming
DCInput = StepCurrent

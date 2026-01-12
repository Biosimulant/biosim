# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Synapse modules for the neuro pack: convert spikes to currents."""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent

from bsim import BioModule


class ExpSynapseCurrent(BioModule):
    """Convert incoming spikes to exponentially decaying synaptic current.

    Creates a static random connectivity matrix from pre to post neurons.
    On each spike from pre-synaptic neurons, increments post-synaptic currents.
    Decays currents exponentially each step.

    Parameters:
        n_pre: Number of pre-synaptic neurons (spike sources).
        n_post: Number of post-synaptic neurons (current targets).
        p_connect: Connection probability (0-1).
        weight: Synaptic weight (current increment per spike).
        tau: Decay time constant in seconds.
        seed: Random seed for connectivity generation.
        delay_steps: Number of steps to delay spike delivery (default 0).

    Emits:
        current: {"t": float, "I": [float, ...]} per-neuron current for the target population.
    """

    def __init__(
        self,
        n_pre: int = 100,
        n_post: int = 100,
        p_connect: float = 0.1,
        weight: float = 1.0,
        tau: float = 0.01,
        seed: Optional[int] = None,
        delay_steps: int = 0,
    ) -> None:
        self.n_pre = n_pre
        self.n_post = n_post
        self.p_connect = p_connect
        self.weight = weight
        self.tau = tau
        self.seed = seed
        self.delay_steps = delay_steps

        self._rng = random.Random(seed)

        # Build static connectivity: adjacency[pre_idx] = [post_idx, ...]
        self._adjacency: Dict[int, List[int]] = {}
        self._build_connectivity()

        # State
        self._I: List[float] = [0.0] * n_post
        self._spike_buffer: List[List[int]] = []  # For delay
        self._time: float = 0.0
        self._last_dt: float = 0.001

        # History for visualization
        self._current_history: List[List[float]] = []  # [[t, mean_I], ...]

    def _build_connectivity(self) -> None:
        """Build random sparse connectivity matrix."""
        self._adjacency = {}
        for pre in range(self.n_pre):
            targets = []
            for post in range(self.n_post):
                if self._rng.random() < self.p_connect:
                    targets.append(post)
            if targets:
                self._adjacency[pre] = targets

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return {"spikes"}

    def outputs(self) -> Set[str]:
        return {"current"}

    def reset(self) -> None:
        """Reset state for a new simulation run."""
        self._I = [0.0] * self.n_post
        self._spike_buffer = []
        self._time = 0.0
        self._current_history = []
        # Optionally rebuild connectivity with same seed for reproducibility
        self._rng = random.Random(self.seed)
        self._build_connectivity()

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        """Handle incoming spike signals."""
        if topic != "spikes":
            return

        spike_ids = payload.get("ids", [])
        if not spike_ids:
            return

        if self.delay_steps > 0:
            # Buffer spikes for delayed delivery
            self._spike_buffer.append(list(spike_ids))
        else:
            # Apply spikes immediately
            self._apply_spikes(spike_ids)

    def _apply_spikes(self, spike_ids: List[int]) -> None:
        """Apply spikes from pre-synaptic neurons to post-synaptic currents."""
        for pre_idx in spike_ids:
            targets = self._adjacency.get(pre_idx, [])
            for post_idx in targets:
                self._I[post_idx] += self.weight

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        t = float(payload.get("t", self._time))
        dt = t - self._time if t > self._time else self._last_dt
        self._last_dt = dt
        self._time = t

        # Process delayed spikes if any
        if self.delay_steps > 0 and self._spike_buffer:
            # Pop oldest if buffer exceeds delay
            while len(self._spike_buffer) > self.delay_steps:
                delayed_spikes = self._spike_buffer.pop(0)
                self._apply_spikes(delayed_spikes)

        # Decay currents: I = I * exp(-dt / tau)
        decay = 2.718281828 ** (-dt / self.tau) if self.tau > 0 else 0.0
        for i in range(self.n_post):
            self._I[i] *= decay

        # Record history for visualization (mean current)
        mean_I = sum(self._I) / self.n_post if self.n_post > 0 else 0.0
        self._current_history.append([t, mean_I])

        # Emit current to target population
        world.publish_biosignal(self, topic="current", payload={"t": t, "I": list(self._I)})

    def visualize(self) -> Optional[Dict[str, Any]]:
        """Return a timeseries visualization of mean synaptic current."""
        if not self._current_history:
            return None

        weight_sign = "excitatory" if self.weight > 0 else "inhibitory"
        return {
            "render": "timeseries",
            "data": {
                "series": [{"name": "Mean I", "points": self._current_history}],
                "title": f"ExpSynapseCurrent ({self.n_pre}→{self.n_post}, p={self.p_connect})",
            },
            "description": (
                f"Mean synaptic current from {self.n_pre} pre- to {self.n_post} post-synaptic neurons. "
                f"Connection probability: {self.p_connect*100:.0f}%, weight: {self.weight} ({weight_sign}), "
                f"decay τ: {self.tau*1000:.1f}ms. Current rises on incoming spikes and decays exponentially."
            ),
        }

    def get_connectivity_stats(self) -> Dict[str, Any]:
        """Return connectivity statistics (useful for debugging/verification)."""
        total_synapses = sum(len(targets) for targets in self._adjacency.values())
        max_possible = self.n_pre * self.n_post
        return {
            "n_pre": self.n_pre,
            "n_post": self.n_post,
            "n_synapses": total_synapses,
            "density": total_synapses / max_possible if max_possible > 0 else 0,
        }

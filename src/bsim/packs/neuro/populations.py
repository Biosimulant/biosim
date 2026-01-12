# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Population modules for the neuro pack: spiking neuron models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING, Union

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent

from bsim import BioModule


@dataclass
class IzhikevichPreset:
    """Named parameter presets for the Izhikevich model.

    The Izhikevich model: dv/dt = 0.04*v^2 + 5*v + 140 - u + I; du/dt = a*(b*v - u)
    If v >= 30mV: v = c, u = u + d

    Common presets:
        RS (Regular Spiking): a=0.02, b=0.2, c=-65, d=8
        FS (Fast Spiking): a=0.1, b=0.2, c=-65, d=2
        Bursting (Intrinsically Bursting): a=0.02, b=0.2, c=-55, d=4
        Chattering: a=0.02, b=0.2, c=-50, d=2
        LTS (Low-Threshold Spiking): a=0.02, b=0.25, c=-65, d=2
    """
    a: float
    b: float
    c: float
    d: float
    name: str = ""


# Standard presets from Izhikevich (2003)
PRESET_RS = IzhikevichPreset(a=0.02, b=0.2, c=-65.0, d=8.0, name="RS")
PRESET_FS = IzhikevichPreset(a=0.1, b=0.2, c=-65.0, d=2.0, name="FS")
PRESET_BURSTING = IzhikevichPreset(a=0.02, b=0.2, c=-55.0, d=4.0, name="Bursting")
PRESET_CHATTERING = IzhikevichPreset(a=0.02, b=0.2, c=-50.0, d=2.0, name="Chattering")
PRESET_LTS = IzhikevichPreset(a=0.02, b=0.25, c=-65.0, d=2.0, name="LTS")

PRESETS = {
    "RS": PRESET_RS,
    "FS": PRESET_FS,
    "Bursting": PRESET_BURSTING,
    "Chattering": PRESET_CHATTERING,
    "LTS": PRESET_LTS,
}


class IzhikevichPopulation(BioModule):
    """A population of Izhikevich spiking neurons.

    Receives `current` signals and emits `spikes` and `state` signals.

    Parameters:
        n: Number of neurons.
        a, b, c, d: Izhikevich model parameters (or use preset).
        preset: Name of a preset ("RS", "FS", "Bursting", "Chattering", "LTS").
        v_init: Initial membrane potential (default -65mV).
        u_init: Initial recovery variable (default b * v_init).
        I_bias: Constant bias current added to all neurons.
        sample_indices: Indices of neurons to include in state output (default first 5).

    Emits:
        spikes: {"t": float, "ids": [int, ...]} when neurons spike
        state: {"t": float, "indices": [int, ...], "v": [float, ...], "u": [float, ...]}
               sampled state for visualization
    """

    def __init__(
        self,
        n: int = 100,
        a: Optional[float] = None,
        b: Optional[float] = None,
        c: Optional[float] = None,
        d: Optional[float] = None,
        preset: Optional[str] = None,
        v_init: float = -65.0,
        u_init: Optional[float] = None,
        I_bias: float = 0.0,
        sample_indices: Optional[List[int]] = None,
    ) -> None:
        self.n = n
        self.I_bias = I_bias

        # Resolve parameters from preset or direct values
        if preset and preset in PRESETS:
            p = PRESETS[preset]
            self.a = a if a is not None else p.a
            self.b = b if b is not None else p.b
            self.c = c if c is not None else p.c
            self.d = d if d is not None else p.d
        else:
            self.a = a if a is not None else PRESET_RS.a
            self.b = b if b is not None else PRESET_RS.b
            self.c = c if c is not None else PRESET_RS.c
            self.d = d if d is not None else PRESET_RS.d

        self.v_init = v_init
        self.u_init = u_init if u_init is not None else self.b * v_init

        # Sample indices for state output
        default_samples = list(range(min(5, n)))
        self.sample_indices = sample_indices if sample_indices is not None else default_samples

        # State arrays
        self._v: List[float] = []
        self._u: List[float] = []
        self._I_ext: List[float] = []  # External current accumulator
        self._time: float = 0.0
        self._last_dt: float = 0.001

        # History for visualization (sampled neurons)
        self._v_history: Dict[int, List[List[float]]] = {}  # neuron_idx -> [[t, v], ...]

        self._init_state()

    def _init_state(self) -> None:
        """Initialize neuron state arrays."""
        self._v = [self.v_init] * self.n
        self._u = [self.u_init] * self.n
        self._I_ext = [0.0] * self.n
        self._time = 0.0
        self._v_history = {}

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return {"current"}

    def outputs(self) -> Set[str]:
        return {"spikes", "state"}

    def reset(self) -> None:
        """Reset state for a new simulation run."""
        self._init_state()

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        """Handle incoming current signals."""
        if topic != "current":
            return

        I = payload.get("I", 0.0)
        if isinstance(I, (int, float)):
            # Scalar current: apply to all neurons
            for i in range(self.n):
                self._I_ext[i] += float(I)
        elif isinstance(I, (list, tuple)):
            # Per-neuron current
            for i, val in enumerate(I):
                if i < self.n:
                    self._I_ext[i] += float(val)

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

        # Integrate using Euler method
        spiked_ids: List[int] = []
        for i in range(self.n):
            v = self._v[i]
            u = self._u[i]
            I_total = self._I_ext[i] + self.I_bias

            # Izhikevich equations (standard formulation with ms time scale)
            # dv/dt = 0.04*v^2 + 5*v + 140 - u + I
            # du/dt = a*(b*v - u)
            # Using Euler with dt in seconds, scale appropriately
            dt_ms = dt * 1000.0  # Convert to ms for standard Izh params

            # Numerical stability: sub-stepping for large dt
            n_substeps = max(1, int(dt_ms / 0.5))
            sub_dt = dt_ms / n_substeps

            for _ in range(n_substeps):
                dv = (0.04 * v * v + 5.0 * v + 140.0 - u + I_total) * sub_dt
                du = self.a * (self.b * v - u) * sub_dt
                v = v + dv
                u = u + du

                # Spike detection
                if v >= 30.0:
                    v = self.c
                    u = u + self.d
                    if i not in spiked_ids:
                        spiked_ids.append(i)

            self._v[i] = v
            self._u[i] = u

        # Clear external current after integration (it accumulates from signals)
        self._I_ext = [0.0] * self.n

        # Emit spikes
        world.publish_biosignal(self, topic="spikes", payload={"t": t, "ids": spiked_ids})

        # Emit sampled state for visualization
        state_indices = [i for i in self.sample_indices if i < self.n]
        state_v = [self._v[i] for i in state_indices]
        state_u = [self._u[i] for i in state_indices]

        # Record history for visualization
        for idx, v in zip(state_indices, state_v):
            if idx not in self._v_history:
                self._v_history[idx] = []
            self._v_history[idx].append([t, v])

        world.publish_biosignal(
            self,
            topic="state",
            payload={
                "t": t,
                "indices": state_indices,
                "v": state_v,
                "u": state_u,
            },
        )

    def visualize(self) -> Optional[Dict[str, Any]]:
        """Return a timeseries visualization of membrane potentials."""
        if not self._v_history:
            return None

        series_list = []
        for idx in sorted(self._v_history.keys()):
            series_list.append({
                "name": f"Neuron {idx}",
                "points": self._v_history[idx],
            })

        return {
            "render": "timeseries",
            "data": {
                "series": series_list,
                "title": f"IzhikevichPopulation (n={self.n}) Membrane Potential",
            },
        }

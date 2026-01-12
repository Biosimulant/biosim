# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Environment module for the ecology pack: broadcasts environmental conditions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent
    from bsim.visuals import VisualSpec

from bsim import BioModule


class Environment(BioModule):
    """Broadcasts environmental conditions to all connected organism modules.

    On each simulation step, emits a `conditions` signal containing current
    environmental state (temperature, water, food, etc.).

    Parameters:
        temperature: Initial temperature in Celsius.
        water: Initial water availability (0-100 scale).
        food_availability: Food abundance multiplier (0-2 scale, 1 = normal).
        sunlight: Sunlight intensity (0-1 scale).
        temperature_variation: Random variation in temperature per step.
        seasonal_cycle: If True, apply sinusoidal seasonal variation.
        season_period: Period of seasonal cycle in simulation time units.
    """

    def __init__(
        self,
        temperature: float = 25.0,
        water: float = 100.0,
        food_availability: float = 1.0,
        sunlight: float = 1.0,
        temperature_variation: float = 0.0,
        seasonal_cycle: bool = False,
        season_period: float = 365.0,
    ) -> None:
        self._temperature = temperature
        self._water = water
        self._food = food_availability
        self._sunlight = sunlight
        self._temp_variation = temperature_variation
        self._seasonal_cycle = seasonal_cycle
        self._season_period = season_period

        self._base_temperature = temperature
        self._time: float = 0.0
        self._history: List[Dict[str, float]] = []

        # Allow external control to modify these
        self.temperature = temperature
        self.water = water
        self.food_availability = food_availability
        self.sunlight = sunlight

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return set()

    def outputs(self) -> Set[str]:
        return {"conditions"}

    def reset(self) -> None:
        """Reset to initial state."""
        self._time = 0.0
        self._history = []
        self._temperature = self._base_temperature
        self.temperature = self._base_temperature

    def _compute_temperature(self, t: float) -> float:
        """Compute current temperature with optional seasonal cycle."""
        import math
        import random

        temp = self.temperature

        # Apply seasonal variation
        if self._seasonal_cycle:
            # Sinusoidal variation: +/- 15 degrees over the season
            seasonal_offset = 15.0 * math.sin(2 * math.pi * t / self._season_period)
            temp += seasonal_offset

        # Apply random variation
        if self._temp_variation > 0:
            temp += random.gauss(0, self._temp_variation)

        return temp

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        t = float(payload.get("t", self._time))
        self._time = t

        # Compute current environmental state
        current_temp = self._compute_temperature(t)
        self._temperature = current_temp

        conditions = {
            "temperature": current_temp,
            "water": self.water,
            "food": self.food_availability,
            "sunlight": self.sunlight,
            "t": t,
        }

        # Record history
        self._history.append(conditions.copy())

        # Broadcast to all connected modules
        world.publish_biosignal(self, topic="conditions", payload=conditions)

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        pass  # Environment does not receive signals

    def visualize(self) -> Optional["VisualSpec"]:
        """Generate a multi-series timeseries of environmental conditions."""
        if not self._history:
            return None

        return {
            "render": "timeseries",
            "data": {
                "series": [
                    {
                        "name": "Temperature (°C)",
                        "points": [[h["t"], h["temperature"]] for h in self._history],
                    },
                    {
                        "name": "Water (%)",
                        "points": [[h["t"], h["water"]] for h in self._history],
                    },
                    {
                        "name": "Food",
                        "points": [[h["t"], h["food"]] for h in self._history],
                    },
                ],
                "title": "Environmental Conditions",
            },
        }

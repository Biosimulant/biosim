# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Population modules for the ecology pack: organism populations with dynamics."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent
    from bsim.visuals import VisualSpec

from bsim import BioModule


@dataclass
class SpeciesPreset:
    """Preset parameters for common species archetypes."""
    birth_rate: float
    death_rate: float
    optimal_temp: float
    temp_tolerance: float
    water_need: float  # 0-1 scale, how dependent on water
    food_efficiency: float  # How efficiently they convert food to reproduction


# Common species presets
PRESET_RABBIT = SpeciesPreset(
    birth_rate=0.2,
    death_rate=0.05,
    optimal_temp=20.0,
    temp_tolerance=15.0,
    water_need=0.5,
    food_efficiency=0.8,
)

PRESET_FOX = SpeciesPreset(
    birth_rate=0.05,
    death_rate=0.08,
    optimal_temp=15.0,
    temp_tolerance=20.0,
    water_need=0.3,
    food_efficiency=0.6,
)

PRESET_DEER = SpeciesPreset(
    birth_rate=0.1,
    death_rate=0.04,
    optimal_temp=18.0,
    temp_tolerance=18.0,
    water_need=0.6,
    food_efficiency=0.7,
)

PRESET_WOLF = SpeciesPreset(
    birth_rate=0.04,
    death_rate=0.06,
    optimal_temp=10.0,
    temp_tolerance=25.0,
    water_need=0.4,
    food_efficiency=0.5,
)

PRESET_BACTERIA = SpeciesPreset(
    birth_rate=0.8,
    death_rate=0.7,
    optimal_temp=37.0,
    temp_tolerance=10.0,
    water_need=0.9,
    food_efficiency=0.95,
)

PRESETS: Dict[str, SpeciesPreset] = {
    "rabbit": PRESET_RABBIT,
    "fox": PRESET_FOX,
    "deer": PRESET_DEER,
    "wolf": PRESET_WOLF,
    "bacteria": PRESET_BACTERIA,
}


class OrganismPopulation(BioModule):
    """A population of organisms with environmental response and population dynamics.

    Receives environmental `conditions` signals and responds to predation/competition.
    Publishes `population_state` signals with current population count and food demand.

    Population dynamics include:
    - Birth rate modulated by food availability and environmental conditions
    - Death rate modulated by temperature stress, water stress, and predation
    - Carrying capacity limits based on available resources

    Parameters:
        name: Species name for identification.
        initial_count: Starting population size.
        birth_rate: Base birth rate per time unit (0-1).
        death_rate: Base death rate per time unit (0-1).
        optimal_temp: Optimal temperature in Celsius.
        temp_tolerance: Temperature tolerance range (degrees from optimal before stress).
        water_need: Dependence on water (0-1 scale).
        food_efficiency: How efficiently food converts to reproduction (0-1).
        carrying_capacity: Maximum population size (0 = unlimited).
        preset: Optional preset name to use ("rabbit", "fox", "deer", "wolf", "bacteria").
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        name: str = "Species",
        initial_count: int = 100,
        birth_rate: float = 0.1,
        death_rate: float = 0.05,
        optimal_temp: float = 25.0,
        temp_tolerance: float = 10.0,
        water_need: float = 0.5,
        food_efficiency: float = 0.7,
        carrying_capacity: int = 0,
        preset: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.name = name
        self.initial_count = initial_count
        self.count = initial_count
        self.carrying_capacity = carrying_capacity
        self.seed = seed
        self._rng = random.Random(seed)

        # Apply preset if specified
        if preset and preset in PRESETS:
            p = PRESETS[preset]
            self.birth_rate = p.birth_rate
            self.death_rate = p.death_rate
            self.optimal_temp = p.optimal_temp
            self.temp_tolerance = p.temp_tolerance
            self.water_need = p.water_need
            self.food_efficiency = p.food_efficiency
        else:
            self.birth_rate = birth_rate
            self.death_rate = death_rate
            self.optimal_temp = optimal_temp
            self.temp_tolerance = temp_tolerance
            self.water_need = water_need
            self.food_efficiency = food_efficiency

        self._time: float = 0.0
        self._history: List[Dict[str, Any]] = []
        self._current_conditions: Dict[str, float] = {}
        self._pending_deaths: int = 0  # Deaths from predation
        self._food_from_predation: float = 0.0  # Food gained if predator

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return {"conditions", "predation", "competition", "food_gained"}

    def outputs(self) -> Set[str]:
        return {"population_state"}

    def reset(self) -> None:
        """Reset population to initial state."""
        self._rng = random.Random(self.seed)
        self.count = self.initial_count
        self._time = 0.0
        self._history = []
        self._current_conditions = {}
        self._pending_deaths = 0
        self._food_from_predation = 0.0

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic == "conditions":
            self._current_conditions = payload
        elif topic == "predation":
            # Another species is preying on us
            kills = int(payload.get("kills", 0))
            self._pending_deaths += kills
        elif topic == "competition":
            # Competition reduces effective food
            pass  # Handled in on_event
        elif topic == "food_gained":
            # Food from successful predation
            self._food_from_predation += float(payload.get("food", 0.0))

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        t = float(payload.get("t", self._time))
        dt = t - self._time if t > self._time else 0.1
        self._time = t

        if self.count <= 0:
            self._publish_state(t, world)
            return

        # Get environmental conditions
        temp = self._current_conditions.get("temperature", self.optimal_temp)
        water = self._current_conditions.get("water", 100.0)
        food = self._current_conditions.get("food", 1.0)

        # Calculate environmental stress factors
        temp_stress = self._calculate_temp_stress(temp)
        water_stress = self._calculate_water_stress(water)

        # Add food from predation to effective food
        # Predation food is scaled per-capita for better dynamics
        predation_food_per_capita = (
            self._food_from_predation / max(1, self.count)
            if self._food_from_predation > 0 else 0.0
        )
        effective_food = food + predation_food_per_capita * 10  # Scale up predation benefit
        self._food_from_predation = 0.0  # Reset for next step

        # Calculate effective rates
        # Birth rate increases with food, decreases with stress
        # Higher cap allows predators to thrive when hunting is good
        food_factor = min(5.0, effective_food * self.food_efficiency)
        stress_reduction = (1 - temp_stress) * (1 - water_stress * self.water_need)
        effective_birth = self.birth_rate * food_factor * stress_reduction

        # Death rate increases with stress and lack of food
        stress_increase = 1 + temp_stress + water_stress * self.water_need
        # Starvation: if no food from predation and low base food, increase death rate
        if food < 0.5 and predation_food_per_capita < 0.01:
            stress_increase += 0.5  # Starvation stress
        effective_death = self.death_rate * stress_increase

        # Apply carrying capacity pressure
        if self.carrying_capacity > 0 and self.count > self.carrying_capacity * 0.5:
            overcrowding = self.count / self.carrying_capacity
            effective_death *= (1 + overcrowding)
            effective_birth *= max(0, 1 - overcrowding * 0.5)

        # Calculate births and deaths (stochastic)
        expected_births = self.count * effective_birth * dt
        expected_deaths = self.count * effective_death * dt

        # Poisson-like sampling for integer counts
        births = self._poisson_sample(expected_births)
        natural_deaths = self._poisson_sample(expected_deaths)

        # Apply pending deaths from predation
        predation_deaths = min(self._pending_deaths, self.count)
        self._pending_deaths = 0

        total_deaths = natural_deaths + predation_deaths

        # Update population
        self.count = max(0, self.count + births - total_deaths)

        # Apply carrying capacity hard limit
        if self.carrying_capacity > 0:
            self.count = min(self.count, self.carrying_capacity)

        # Record history
        self._history.append({
            "t": t,
            "count": self.count,
            "births": births,
            "deaths": total_deaths,
            "predation_deaths": predation_deaths,
            "temp_stress": temp_stress,
            "water_stress": water_stress,
            "effective_birth": effective_birth,
            "effective_death": effective_death,
        })

        # Publish state
        self._publish_state(t, world)

    def _calculate_temp_stress(self, temp: float) -> float:
        """Calculate temperature stress (0 = ideal, 1 = lethal)."""
        deviation = abs(temp - self.optimal_temp)
        stress = deviation / self.temp_tolerance
        return min(1.0, max(0.0, stress))

    def _calculate_water_stress(self, water: float) -> float:
        """Calculate water stress based on availability."""
        # Stress increases as water drops below 50%
        if water >= 50.0:
            return 0.0
        return (50.0 - water) / 50.0

    def _poisson_sample(self, expected: float) -> int:
        """Sample from a Poisson-like distribution."""
        if expected <= 0:
            return 0
        if expected > 100:
            # For large values, use normal approximation
            return max(0, int(self._rng.gauss(expected, expected ** 0.5)))
        # For small values, use actual Poisson
        import math
        L = math.exp(-expected)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= self._rng.random()
        return k - 1

    def _publish_state(self, t: float, world: "BioWorld") -> None:
        """Publish current population state."""
        world.publish_biosignal(self, topic="population_state", payload={
            "species": self.name,
            "count": self.count,
            "t": t,
        })

    def visualize(self) -> Optional["VisualSpec"]:
        """Generate population count timeseries visualization."""
        if not self._history:
            return None

        return {
            "render": "timeseries",
            "data": {
                "series": [
                    {
                        "name": f"{self.name} Count",
                        "points": [[h["t"], h["count"]] for h in self._history],
                    },
                ],
                "title": f"{self.name} Population",
            },
        }


class Prey(OrganismPopulation):
    """Convenience class for prey species (rabbit preset by default)."""

    def __init__(
        self,
        name: str = "Prey",
        initial_count: int = 500,
        preset: str = "rabbit",
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, initial_count=initial_count, preset=preset, **kwargs)


class Predator(OrganismPopulation):
    """Convenience class for predator species (fox preset by default).

    Predators require food from hunting to maintain birth rates.
    Without prey, their population will decline.
    """

    def __init__(
        self,
        name: str = "Predator",
        initial_count: int = 50,
        preset: str = "fox",
        base_food: float = 0.1,  # Minimal food without hunting
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, initial_count=initial_count, preset=preset, **kwargs)
        self.base_food = base_food

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        # Modify conditions to reduce base food for predators
        # They rely on predation for food
        if self._current_conditions:
            self._current_conditions = dict(self._current_conditions)
            self._current_conditions["food"] = self.base_food

        super().on_event(event, payload, world)

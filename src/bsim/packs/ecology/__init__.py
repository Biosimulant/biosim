# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Ecology pack: reference modules for population and ecosystem simulations.

This pack provides composable BioModules for simulating ecological dynamics
including predator-prey interactions, competition, and environmental effects.

Environment:
    Environment - Broadcast environmental conditions (temperature, water, food)

Populations:
    OrganismPopulation - Generic population with birth/death dynamics
    Prey - Convenience class for prey species (rabbit preset)
    Predator - Convenience class for predator species (fox preset)

Interactions:
    PredatorPreyInteraction - Lotka-Volterra style predation
    CompetitionInteraction - Resource competition between species
    MutualismInteraction - Beneficial inter-species relationships

Monitors:
    PopulationMonitor - Collect and plot population timeseries
    EcologyMetrics - Compute summary statistics (diversity, extinctions, etc.)
    PhaseSpaceMonitor - 2D phase space plot of two populations

Presets:
    PRESET_RABBIT - Fast-breeding herbivore
    PRESET_FOX - Moderate predator
    PRESET_DEER - Large herbivore
    PRESET_WOLF - Apex predator
    PRESET_BACTERIA - Rapidly reproducing microorganism
    PRESETS - Dict of all presets by name
    SpeciesPreset - Dataclass for custom presets

Example:
    from bsim.packs.ecology import (
        Environment,
        OrganismPopulation,
        PredatorPreyInteraction,
        PopulationMonitor,
        PRESET_RABBIT,
    )
"""

from .environment import Environment
from .populations import (
    OrganismPopulation,
    Prey,
    Predator,
    SpeciesPreset,
    PRESET_RABBIT,
    PRESET_FOX,
    PRESET_DEER,
    PRESET_WOLF,
    PRESET_BACTERIA,
    PRESETS,
)
from .interactions import (
    PredatorPreyInteraction,
    CompetitionInteraction,
    MutualismInteraction,
)
from .monitors import (
    PopulationMonitor,
    EcologyMetrics,
    PhaseSpaceMonitor,
)

__all__ = [
    # Environment
    "Environment",
    # Populations
    "OrganismPopulation",
    "Prey",
    "Predator",
    "SpeciesPreset",
    "PRESET_RABBIT",
    "PRESET_FOX",
    "PRESET_DEER",
    "PRESET_WOLF",
    "PRESET_BACTERIA",
    "PRESETS",
    # Interactions
    "PredatorPreyInteraction",
    "CompetitionInteraction",
    "MutualismInteraction",
    # Monitors
    "PopulationMonitor",
    "EcologyMetrics",
    "PhaseSpaceMonitor",
]

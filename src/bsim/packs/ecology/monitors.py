# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Monitor modules for the ecology pack: collect data and produce visualizations."""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent
    from bsim.visuals import VisualSpec

from bsim import BioModule


class PopulationMonitor(BioModule):
    """Collects population data from multiple species and visualizes them together.

    Receives `population_state` signals and produces a combined timeseries plot.

    Parameters:
        max_points: Maximum data points per species (oldest dropped).
    """

    def __init__(self, max_points: int = 10000) -> None:
        self.max_points = max_points
        self._data: Dict[str, List[Dict[str, float]]] = {}

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()

    def inputs(self) -> Set[str]:
        return {"population_state"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        """Reset collected data."""
        self._data = {}

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "population_state":
            return

        species = str(payload.get("species", "Unknown"))
        count = int(payload.get("count", 0))
        t = float(payload.get("t", 0.0))

        if species not in self._data:
            self._data[species] = []

        self._data[species].append({"t": t, "count": count})

        # Trim if over limit
        if len(self._data[species]) > self.max_points:
            self._data[species] = self._data[species][-self.max_points:]

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        pass

    def visualize(self) -> Optional["VisualSpec"]:
        """Generate combined population timeseries for all species."""
        if not self._data:
            return None

        series = []
        for species in sorted(self._data.keys()):
            history = self._data[species]
            series.append({
                "name": species,
                "points": [[h["t"], h["count"]] for h in history],
            })

        return {
            "render": "timeseries",
            "data": {
                "series": series,
                "title": "Population Dynamics",
            },
        }


class EcologyMetrics(BioModule):
    """Compute summary statistics for ecological simulations.

    Produces a table with metrics like:
    - Total population across all species
    - Species diversity (Shannon index)
    - Population stability (coefficient of variation)
    - Extinction events
    """

    def __init__(self) -> None:
        self._populations: Dict[str, List[int]] = {}
        self._extinctions: Dict[str, float] = {}  # species -> extinction time
        self._t_start: Optional[float] = None
        self._t_end: float = 0.0

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()

    def inputs(self) -> Set[str]:
        return {"population_state"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        self._populations = {}
        self._extinctions = {}
        self._t_start = None
        self._t_end = 0.0

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "population_state":
            return

        species = str(payload.get("species", "Unknown"))
        count = int(payload.get("count", 0))
        t = float(payload.get("t", 0.0))

        if self._t_start is None:
            self._t_start = t
        self._t_end = t

        if species not in self._populations:
            self._populations[species] = []

        self._populations[species].append(count)

        # Track extinctions
        if count == 0 and species not in self._extinctions:
            self._extinctions[species] = t

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        pass

    def _compute_shannon_diversity(self) -> float:
        """Compute Shannon diversity index from final populations."""
        import math

        final_pops = {}
        for species, history in self._populations.items():
            if history:
                final_pops[species] = history[-1]

        total = sum(final_pops.values())
        if total <= 0:
            return 0.0

        H = 0.0
        for count in final_pops.values():
            if count > 0:
                p = count / total
                H -= p * math.log(p)

        return H

    def _compute_cv(self, values: List[int]) -> Optional[float]:
        """Compute coefficient of variation."""
        if len(values) < 2:
            return None

        mean = sum(values) / len(values)
        if mean <= 0:
            return None

        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance ** 0.5
        return std / mean

    def visualize(self) -> Optional["VisualSpec"]:
        """Generate ecology metrics table."""
        duration = self._t_end - (self._t_start or 0.0)

        # Compute metrics
        final_total = sum(
            history[-1] if history else 0
            for history in self._populations.values()
        )

        n_species = len(self._populations)
        n_extinct = len(self._extinctions)
        n_surviving = n_species - n_extinct

        shannon = self._compute_shannon_diversity()

        # Average CV across species (population stability)
        cvs = []
        for history in self._populations.values():
            cv = self._compute_cv(history)
            if cv is not None:
                cvs.append(cv)
        avg_cv = sum(cvs) / len(cvs) if cvs else 0.0

        # Peak total population
        max_totals = []
        if self._populations:
            first_species = list(self._populations.keys())[0]
            n_steps = len(self._populations[first_species])
            for i in range(n_steps):
                total = sum(
                    history[i] if i < len(history) else 0
                    for history in self._populations.values()
                )
                max_totals.append(total)
        peak_pop = max(max_totals) if max_totals else 0

        rows = [
            ["Duration (time units)", f"{duration:.2f}"],
            ["Number of Species", str(n_species)],
            ["Surviving Species", str(n_surviving)],
            ["Extinctions", str(n_extinct)],
            ["Final Total Population", str(final_total)],
            ["Peak Total Population", str(peak_pop)],
            ["Shannon Diversity Index", f"{shannon:.3f}"],
            ["Avg Population CV", f"{avg_cv:.3f}"],
        ]

        # Add extinction details
        if self._extinctions:
            for species, ext_time in sorted(self._extinctions.items()):
                rows.append([f"  {species} Extinct at", f"t={ext_time:.2f}"])

        return {
            "render": "table",
            "data": {
                "columns": ["Metric", "Value"],
                "rows": rows,
            },
        }


class PhaseSpaceMonitor(BioModule):
    """Creates a phase space plot of two populations.

    Useful for visualizing predator-prey dynamics in 2D space.

    Parameters:
        x_species: Name of species for X axis.
        y_species: Name of species for Y axis.
        max_points: Maximum points to store.
    """

    def __init__(
        self,
        x_species: str = "Prey",
        y_species: str = "Predator",
        max_points: int = 5000,
    ) -> None:
        self.x_species = x_species
        self.y_species = y_species
        self.max_points = max_points

        self._x_values: List[int] = []
        self._y_values: List[int] = []
        self._current_x: int = 0
        self._current_y: int = 0
        self._time: float = 0.0

    def subscriptions(self) -> Set["BioWorldEvent"]:
        from bsim import BioWorldEvent
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return {"population_state"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        self._x_values = []
        self._y_values = []
        self._current_x = 0
        self._current_y = 0
        self._time = 0.0

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "population_state":
            return

        species = str(payload.get("species", ""))
        count = int(payload.get("count", 0))

        if species == self.x_species:
            self._current_x = count
        elif species == self.y_species:
            self._current_y = count

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        from bsim import BioWorldEvent
        if event != BioWorldEvent.STEP:
            return

        # Record current point
        self._x_values.append(self._current_x)
        self._y_values.append(self._current_y)

        # Trim if over limit
        if len(self._x_values) > self.max_points:
            self._x_values = self._x_values[-self.max_points:]
            self._y_values = self._y_values[-self.max_points:]

    def visualize(self) -> Optional["VisualSpec"]:
        """Generate SVG phase space plot."""
        if len(self._x_values) < 2:
            return None

        svg = self._generate_phase_svg()
        svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data_uri = f"data:image/svg+xml;base64,{svg_b64}"

        return {
            "render": "image",
            "data": {
                "src": data_uri,
                "alt": f"Phase space: {self.x_species} vs {self.y_species}",
                "width": 500,
                "height": 400,
            },
        }

    def _generate_phase_svg(self) -> str:
        """Generate SVG phase space plot."""
        w, h = 500, 400
        margin = {"top": 30, "right": 30, "bottom": 50, "left": 60}
        plot_w = w - margin["left"] - margin["right"]
        plot_h = h - margin["top"] - margin["bottom"]

        # Determine ranges
        x_min = min(self._x_values) if self._x_values else 0
        x_max = max(self._x_values) if self._x_values else 1
        y_min = min(self._y_values) if self._y_values else 0
        y_max = max(self._y_values) if self._y_values else 1

        # Add padding
        x_range = x_max - x_min if x_max > x_min else 1
        y_range = y_max - y_min if y_max > y_min else 1
        x_min -= x_range * 0.05
        x_max += x_range * 0.05
        y_min -= y_range * 0.05
        y_max += y_range * 0.05

        def x_scale(v: float) -> float:
            return margin["left"] + ((v - x_min) / (x_max - x_min)) * plot_w

        def y_scale(v: float) -> float:
            return margin["top"] + (1 - (v - y_min) / (y_max - y_min)) * plot_h

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            '  <style>',
            '    .axis { stroke: #333; stroke-width: 1; }',
            '    .label { font-family: sans-serif; font-size: 11px; fill: #333; }',
            '    .title { font-family: sans-serif; font-size: 13px; fill: #333; font-weight: bold; }',
            '    .trajectory { fill: none; stroke: #2563eb; stroke-width: 1.5; opacity: 0.7; }',
            '    .start { fill: #22c55e; }',
            '    .end { fill: #ef4444; }',
            '  </style>',
            f'  <rect width="{w}" height="{h}" fill="white"/>',
        ]

        # Draw axes
        x0 = margin["left"]
        x1 = margin["left"] + plot_w
        y0 = margin["top"]
        y1 = margin["top"] + plot_h

        lines.append(f'  <line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
        lines.append(f'  <line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}"/>')

        # X-axis label
        lines.append(f'  <text class="label" x="{x0 + plot_w/2}" y="{h - 10}" text-anchor="middle">{self.x_species}</text>')

        # Y-axis label
        lines.append(f'  <text class="label" x="15" y="{y0 + plot_h/2}" text-anchor="middle" transform="rotate(-90, 15, {y0 + plot_h/2})">{self.y_species}</text>')

        # Title
        lines.append(f'  <text class="title" x="{w/2}" y="18" text-anchor="middle">Phase Space</text>')

        # Draw trajectory
        if len(self._x_values) >= 2:
            points = []
            for x, y in zip(self._x_values, self._y_values):
                px = x_scale(x)
                py = y_scale(y)
                points.append(f"{px},{py}")

            path_d = "M " + " L ".join(points)
            lines.append(f'  <path class="trajectory" d="{path_d}"/>')

            # Start point (green)
            sx, sy = x_scale(self._x_values[0]), y_scale(self._y_values[0])
            lines.append(f'  <circle class="start" cx="{sx}" cy="{sy}" r="5"/>')

            # End point (red)
            ex, ey = x_scale(self._x_values[-1]), y_scale(self._y_values[-1])
            lines.append(f'  <circle class="end" cx="{ex}" cy="{ey}" r="5"/>')

        lines.append('</svg>')
        return "\n".join(lines)

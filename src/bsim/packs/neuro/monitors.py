# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Monitor/probe modules for the neuro pack: collect data and produce visuals."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
import base64

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bsim import BioWorld, BioWorldEvent
    from bsim.visuals import VisualSpec

from bsim import BioModule


def _escape_svg_text(s: str) -> str:
    """Escape text for safe SVG embedding."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class SpikeMonitor(BioModule):
    """Collect spike events and produce a raster plot visualization.

    Receives `spikes` signals and stores events for visualization.
    Produces an SVG raster plot as an `image` VisualSpec.

    Parameters:
        max_events: Maximum number of spike events to store (oldest dropped).
        max_neurons: Maximum neuron index to display in raster (for limiting plot size).
        width: SVG width in pixels.
        height: SVG height in pixels.
    """

    def __init__(
        self,
        max_events: int = 10000,
        max_neurons: Optional[int] = None,
        width: int = 600,
        height: int = 300,
    ) -> None:
        self.max_events = max_events
        self.max_neurons = max_neurons
        self.width = width
        self.height = height

        self._events: List[tuple] = []  # [(t, neuron_id), ...]
        self._t_min: float = float("inf")
        self._t_max: float = float("-inf")
        self._neuron_max: int = 0

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()  # Only receives signals, not world events

    def inputs(self) -> Set[str]:
        return {"spikes"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        """Reset collected data for a new simulation run."""
        self._events = []
        self._t_min = float("inf")
        self._t_max = float("-inf")
        self._neuron_max = 0

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "spikes":
            return

        t = float(payload.get("t", 0.0))
        ids = payload.get("ids", [])

        self._t_min = min(self._t_min, t)
        self._t_max = max(self._t_max, t)

        for nid in ids:
            nid = int(nid)
            self._neuron_max = max(self._neuron_max, nid)
            self._events.append((t, nid))

        # Trim if over limit
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events:]
            # Recompute t_min from remaining events
            if self._events:
                self._t_min = min(e[0] for e in self._events)

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        pass  # No world event handling needed

    def visualize(self) -> Optional["VisualSpec"]:
        """Generate an SVG raster plot of collected spikes."""
        description = (
            "Spike raster plot showing neural activity over time. "
            "Each row represents a neuron, and each vertical tick marks a spike event. "
            "Dense regions indicate high synchronous activity across the population."
        )

        if not self._events:
            # Return empty placeholder
            empty_svg = self._generate_empty_svg()
            empty_b64 = base64.b64encode(empty_svg.encode("utf-8")).decode("ascii")
            return {
                "render": "image",
                "data": {
                    "src": f"data:image/svg+xml;base64,{empty_b64}",
                    "alt": "Raster plot (no spikes)",
                    "width": self.width,
                    "height": self.height,
                },
                "description": description,
            }

        svg = self._generate_raster_svg()
        # Use data URI with base64 encoding for reliable rendering
        svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data_uri = f"data:image/svg+xml;base64,{svg_b64}"

        return {
            "render": "image",
            "data": {
                "src": data_uri,
                "alt": f"Raster plot ({len(self._events)} spikes)",
                "width": self.width,
                "height": self.height,
            },
            "description": description,
        }

    def _generate_empty_svg(self) -> str:
        """Generate an empty placeholder SVG."""
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
  <rect width="100%" height="100%" fill="#f8f8f8"/>
  <text x="50%" y="50%" text-anchor="middle" fill="#999" font-family="sans-serif" font-size="14">No spikes recorded</text>
</svg>"""

    def _generate_raster_svg(self) -> str:
        """Generate an SVG raster plot from collected spike events."""
        w = self.width
        h = self.height
        margin = {"top": 20, "right": 20, "bottom": 40, "left": 50}
        plot_w = w - margin["left"] - margin["right"]
        plot_h = h - margin["top"] - margin["bottom"]

        # Determine ranges
        t_min = self._t_min if self._t_min != float("inf") else 0.0
        t_max = self._t_max if self._t_max != float("-inf") else 1.0
        t_range = t_max - t_min if t_max > t_min else 1.0

        n_max = self.max_neurons if self.max_neurons is not None else self._neuron_max
        n_max = max(n_max, 1)

        # Scale functions
        def x_scale(t: float) -> float:
            return margin["left"] + ((t - t_min) / t_range) * plot_w

        def y_scale(nid: int) -> float:
            return margin["top"] + (1 - nid / n_max) * plot_h

        # Build SVG
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            '  <style>',
            '    .axis { stroke: #333; stroke-width: 1; }',
            '    .tick { stroke: #333; stroke-width: 1; }',
            '    .label { font-family: sans-serif; font-size: 10px; fill: #333; }',
            '    .title { font-family: sans-serif; font-size: 12px; fill: #333; font-weight: bold; }',
            '    .spike { stroke: #2563eb; stroke-width: 1; }',
            '  </style>',
            f'  <rect width="{w}" height="{h}" fill="white"/>',
        ]

        # Draw axes
        x0 = margin["left"]
        x1 = margin["left"] + plot_w
        y0 = margin["top"]
        y1 = margin["top"] + plot_h

        lines.append(f'  <line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')  # x-axis
        lines.append(f'  <line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}"/>')  # y-axis

        # X-axis ticks and labels
        n_xticks = 5
        for i in range(n_xticks + 1):
            t_val = t_min + (i / n_xticks) * t_range
            x_pos = x_scale(t_val)
            lines.append(f'  <line class="tick" x1="{x_pos}" y1="{y1}" x2="{x_pos}" y2="{y1 + 5}"/>')
            lines.append(f'  <text class="label" x="{x_pos}" y="{y1 + 18}" text-anchor="middle">{t_val:.2f}</text>')

        # Y-axis ticks and labels
        n_yticks = min(5, n_max)
        for i in range(n_yticks + 1):
            n_val = int((i / n_yticks) * n_max)
            y_pos = y_scale(n_val)
            lines.append(f'  <line class="tick" x1="{x0 - 5}" y1="{y_pos}" x2="{x0}" y2="{y_pos}"/>')
            lines.append(f'  <text class="label" x="{x0 - 8}" y="{y_pos + 3}" text-anchor="end">{n_val}</text>')

        # Axis labels
        lines.append(f'  <text class="label" x="{x0 + plot_w / 2}" y="{h - 5}" text-anchor="middle">Time (s)</text>')
        lines.append(f'  <text class="label" x="12" y="{y0 + plot_h / 2}" text-anchor="middle" transform="rotate(-90, 12, {y0 + plot_h / 2})">Neuron</text>')

        # Draw spikes as short vertical lines
        for t, nid in self._events:
            if self.max_neurons is not None and nid > self.max_neurons:
                continue
            x_pos = x_scale(t)
            y_pos = y_scale(nid)
            # Small vertical tick for each spike
            lines.append(f'  <line class="spike" x1="{x_pos}" y1="{y_pos - 1}" x2="{x_pos}" y2="{y_pos + 1}"/>')

        lines.append('</svg>')
        return "\n".join(lines)


class RateMonitor(BioModule):
    """Compute population firing rate from spike events.

    Receives `spikes` signals, computes instantaneous firing rate, and produces
    a timeseries VisualSpec.

    Parameters:
        window_size: Time window in seconds for rate computation.
        n_neurons: Total number of neurons (for rate normalization).
    """

    def __init__(
        self,
        window_size: float = 0.05,
        n_neurons: int = 100,
    ) -> None:
        self.window_size = window_size
        self.n_neurons = n_neurons

        self._spike_times: List[float] = []
        self._rate_series: List[List[float]] = []  # [[t, rate], ...]
        self._last_t: float = 0.0

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()

    def inputs(self) -> Set[str]:
        return {"spikes"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        self._spike_times = []
        self._rate_series = []
        self._last_t = 0.0

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "spikes":
            return

        t = float(payload.get("t", 0.0))
        ids = payload.get("ids", [])

        # Record all spike times
        for _ in ids:
            self._spike_times.append(t)

        # Compute rate at this time point
        # Count spikes in [t - window, t]
        window_start = t - self.window_size
        n_in_window = sum(1 for st in self._spike_times if st >= window_start)

        # Rate = (spikes in window) / (window_size * n_neurons) in Hz
        rate = n_in_window / (self.window_size * self.n_neurons) if self.n_neurons > 0 else 0.0
        self._rate_series.append([t, rate])
        self._last_t = t

        # Trim old spike times for memory efficiency
        self._spike_times = [st for st in self._spike_times if st >= window_start]

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        pass

    def visualize(self) -> Optional["VisualSpec"]:
        if not self._rate_series:
            return None

        return {
            "render": "timeseries",
            "data": {
                "series": [
                    {"name": "Population Rate (Hz)", "points": self._rate_series}
                ]
            },
            "description": (
                f"Population firing rate computed over a {self.window_size*1000:.0f}ms sliding window. "
                f"Rate = (spikes in window) / (window size × {self.n_neurons} neurons). "
                "Higher values indicate more synchronized or active network states."
            ),
        }


class StateMonitor(BioModule):
    """Record membrane potential traces from state signals.

    Receives `state` signals (from IzhikevichPopulation) and produces
    a timeseries VisualSpec of voltage traces.

    Parameters:
        max_points: Maximum points per series (oldest dropped).
    """

    def __init__(self, max_points: int = 5000) -> None:
        self.max_points = max_points
        self._series: Dict[int, List[List[float]]] = {}  # neuron_idx -> [[t, v], ...]

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()

    def inputs(self) -> Set[str]:
        return {"state"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        self._series = {}

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "state":
            return

        t = float(payload.get("t", 0.0))
        indices = payload.get("indices", [])
        v_vals = payload.get("v", [])

        for idx, v in zip(indices, v_vals):
            if idx not in self._series:
                self._series[idx] = []
            self._series[idx].append([t, float(v)])

            # Trim if over limit
            if len(self._series[idx]) > self.max_points:
                self._series[idx] = self._series[idx][-self.max_points:]

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        pass

    def visualize(self) -> Optional["VisualSpec"]:
        if not self._series:
            return None

        series_list = []
        for idx in sorted(self._series.keys()):
            series_list.append({
                "name": f"Neuron {idx} Vm (mV)",
                "points": self._series[idx],
            })

        return {
            "render": "timeseries",
            "data": {"series": series_list},
            "description": (
                "Membrane potential (Vm) traces of sampled neurons over time. "
                "Sharp upward deflections reaching ~30mV indicate action potentials (spikes). "
                "After spiking, the membrane resets to a lower potential before gradually depolarizing again."
            ),
        }


class NeuroMetrics(BioModule):
    """Compute summary statistics from spike data.

    Receives `spikes` signals and produces a table VisualSpec with metrics:
    - Total spike count
    - Mean firing rate
    - Number of active neurons
    - Coefficient of variation (CV) of ISIs

    Parameters:
        n_neurons: Total number of neurons (for rate calculation).
    """

    def __init__(self, n_neurons: int = 100) -> None:
        self.n_neurons = n_neurons

        self._spike_count: int = 0
        self._active_neurons: Set[int] = set()
        self._spike_times_by_neuron: Dict[int, List[float]] = {}
        self._t_start: Optional[float] = None
        self._t_end: float = 0.0

    def subscriptions(self) -> Set["BioWorldEvent"]:
        return set()

    def inputs(self) -> Set[str]:
        return {"spikes"}

    def outputs(self) -> Set[str]:
        return set()

    def reset(self) -> None:
        self._spike_count = 0
        self._active_neurons = set()
        self._spike_times_by_neuron = {}
        self._t_start = None
        self._t_end = 0.0

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: "BioWorld",
    ) -> None:
        if topic != "spikes":
            return

        t = float(payload.get("t", 0.0))
        ids = payload.get("ids", [])

        if self._t_start is None:
            self._t_start = t
        self._t_end = t

        for nid in ids:
            nid = int(nid)
            self._spike_count += 1
            self._active_neurons.add(nid)

            if nid not in self._spike_times_by_neuron:
                self._spike_times_by_neuron[nid] = []
            self._spike_times_by_neuron[nid].append(t)

    def on_event(
        self, event: "BioWorldEvent", payload: Dict[str, Any], world: "BioWorld"
    ) -> None:
        pass

    def _compute_cv(self) -> Optional[float]:
        """Compute coefficient of variation of inter-spike intervals."""
        all_isis: List[float] = []
        for times in self._spike_times_by_neuron.values():
            if len(times) >= 2:
                sorted_times = sorted(times)
                for i in range(1, len(sorted_times)):
                    isi = sorted_times[i] - sorted_times[i - 1]
                    if isi > 0:
                        all_isis.append(isi)

        if len(all_isis) < 2:
            return None

        mean_isi = sum(all_isis) / len(all_isis)
        if mean_isi <= 0:
            return None

        variance = sum((isi - mean_isi) ** 2 for isi in all_isis) / len(all_isis)
        std_isi = variance ** 0.5
        return std_isi / mean_isi

    def visualize(self) -> Optional["VisualSpec"]:
        duration = self._t_end - (self._t_start or 0.0) if self._t_start is not None else 0.0

        # Mean rate in Hz (spikes per second per neuron)
        if duration > 0 and self.n_neurons > 0:
            mean_rate = self._spike_count / (duration * self.n_neurons)
        else:
            mean_rate = 0.0

        cv = self._compute_cv()

        rows = [
            ["Total Spikes", str(self._spike_count)],
            ["Active Neurons", str(len(self._active_neurons))],
            ["Duration (s)", f"{duration:.3f}"],
            ["Mean Rate (Hz)", f"{mean_rate:.2f}"],
            ["ISI CV", f"{cv:.3f}" if cv is not None else "N/A"],
        ]

        return {
            "render": "table",
            "data": {
                "columns": ["Metric", "Value"],
                "rows": rows,
            },
            "description": (
                "Summary statistics of neural activity. "
                "ISI CV (coefficient of variation of inter-spike intervals) measures firing regularity: "
                "CV≈0 = perfectly regular, CV≈1 = Poisson-like irregular, CV>1 = bursty firing patterns."
            ),
        }

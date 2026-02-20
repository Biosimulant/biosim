"""Example launching the SimUI with multiple BioModules each exposing different visuals.

Run:
    PYTHONPATH=src python examples/multi_module_ui_demo.py
"""
from __future__ import annotations

import math
import random

import biosim


class SineWave(biosim.BioModule):
    def __init__(self):
        self.min_dt = 0.1
        self.points = []

    def reset(self):
        self.points = []

    def advance_to(self, t: float) -> None:
        self.points.append([t, math.sin(t)])

    def get_outputs(self):
        return {}

    def _decimate(self, pts, max_points=500):
        n = len(pts)
        if n <= max_points:
            return pts
        buckets = max(1, max_points // 2)
        bucket_size = n / buckets
        out = []
        i = 0.0
        for _ in range(buckets):
            start = int(round(i))
            i += bucket_size
            end = int(round(i))
            if end <= start:
                end = min(n, start + 1)
            chunk = pts[start:end]
            if not chunk:
                continue
            min_p = min(chunk, key=lambda p: p[1])
            max_p = max(chunk, key=lambda p: p[1])
            if min_p[0] <= max_p[0]:
                if not out or out[-1] != min_p:
                    out.append(min_p)
                if max_p != min_p:
                    out.append(max_p)
            else:
                if not out or out[-1] != max_p:
                    out.append(max_p)
                if min_p != max_p:
                    out.append(min_p)
        if out and out[0] != pts[0]:
            out.insert(0, pts[0])
        if out and out[-1] != pts[-1]:
            out.append(pts[-1])
        return out[:max_points]

    def visualize(self):
        pts = self._decimate(self.points, max_points=500)
        return {"render": "timeseries", "data": {"series": [{"name": "sin(t)", "points": pts}]}}


class BarCounts(biosim.BioModule):
    def __init__(self):
        self.min_dt = 0.1
        self.values = {"A": 1, "B": 2, "C": 3}
        self._i = 0

    def reset(self):
        self.values = {"A": 1, "B": 2, "C": 3}
        self._i = 0

    def advance_to(self, t: float) -> None:
        self._i += 1
        key = random.choice(list(self.values.keys()))
        self.values[key] += random.randint(0, 2)

    def get_outputs(self):
        return {}

    def visualize(self):
        items = [{"label": k, "value": v} for k, v in self.values.items()]
        return {"render": "bar", "data": {"items": items}}


class TableSnapshot(biosim.BioModule):
    def __init__(self, bar_mod: BarCounts):
        self.min_dt = 0.1
        self.bar_mod = bar_mod
        self.snap = []
        self._i = 0

    def reset(self):
        self.snap = []
        self._i = 0

    def advance_to(self, t: float) -> None:
        self._i += 1
        if self._i % 10 == 0:
            total = sum(self.bar_mod.values.values())
            self.snap.append({"step": self._i, "total": total})
            self.snap = self.snap[-100:]

    def get_outputs(self):
        return {}

    def visualize(self):
        items = self.snap[-4000:]
        return {"render": "table", "data": {"items": items}}


class SmallGraph(biosim.BioModule):
    def __init__(self):
        self.min_dt = 0.5

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        return {}

    def visualize(self):
        return {
            "render": "graph",
            "data": {
                "nodes": [{"id": "sine"}, {"id": "bar"}, {"id": "table"}],
                "edges": [
                    {"source": "sine", "target": "bar"},
                    {"source": "bar", "target": "table"},
                ],
            },
        }


def main():
    world = biosim.BioWorld()
    bar = BarCounts()
    world.add_biomodule("sine", SineWave())
    world.add_biomodule("bar", bar)
    world.add_biomodule("table", TableSnapshot(bar))
    world.add_biomodule("graph", SmallGraph())

    ui = biosim.simui.Interface(
        world,
        title="Multi-Module Demo",
        controls=[
            biosim.simui.Number("duration", 10.0),
            biosim.simui.Number("tick_dt", 0.1),
            biosim.simui.Button("Run"),
        ],
    )
    ui.launch(open_browser=True)


if __name__ == "__main__":
    main()


def test_collect_visuals_empty(biosim):
    world = biosim.BioWorld()

    class Silent(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world.add_biomodule("silent", Silent())
    world.run(duration=0.1, tick_dt=0.1)
    collected = world.collect_visuals()
    assert collected == []


def test_collect_visuals_with_modules(biosim):
    world = biosim.BioWorld()

    class TS(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._points = []

        def advance_to(self, t: float) -> None:
            self._points.append([t, len(self._points)])

        def get_outputs(self):
            return {}

        def visualize(self):
            return {
                "render": "timeseries",
                "data": {"series": [{"name": "i", "points": self._points}]},
            }

    class GraphMod(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

        def visualize(self):
            return {
                "render": "graph",
                "data": {
                    "nodes": [{"id": "a"}, {"id": "b"}],
                    "edges": [{"source": "a", "target": "b"}],
                },
            }

    world.add_biomodule("ts", TS())
    world.add_biomodule("graph", GraphMod())
    world.run(duration=0.2, tick_dt=0.1)

    collected = world.collect_visuals()
    assert len(collected) == 2
    kinds = {entry["module"]: entry for entry in collected}
    assert "TS" in kinds and "GraphMod" in kinds
    ts_vis = kinds["TS"]["visuals"][0]
    assert ts_vis["render"] == "timeseries"
    g_vis = kinds["GraphMod"]["visuals"][0]
    assert g_vis["render"] == "graph"


def test_visuals_invalid_shapes_are_filtered(biosim):
    world = biosim.BioWorld()

    class Bad1(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

        def visualize(self):
            return {"data": {"x": 1}}  # missing 'render'

    class Bad2(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

        def visualize(self):
            return {"render": "timeseries", "data": set([1, 2, 3])}  # not JSON-serializable

    class Good(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

        def visualize(self):
            return {"render": "bar", "data": {"items": [{"label": "a", "value": 1}]}}

    world.add_biomodule("bad1", Bad1())
    world.add_biomodule("bad2", Bad2())
    world.add_biomodule("good", Good())
    world.run(duration=0.1, tick_dt=0.1)

    collected = world.collect_visuals()
    assert len(collected) == 1
    assert collected[0]["module"] == "Good"
    assert collected[0]["visuals"][0]["render"] == "bar"


def test_visuals_description_is_preserved(biosim):
    world = biosim.BioWorld()

    class WithDescription(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

        def visualize(self):
            return {"render": "bar", "data": {"items": [{"label": "a", "value": 1}]}, "description": "hello"}

    world.add_biomodule("desc", WithDescription())
    world.run(duration=0.1, tick_dt=0.1)

    collected = world.collect_visuals()
    assert collected[0]["module"] == "WithDescription"
    assert collected[0]["visuals"][0]["description"] == "hello"

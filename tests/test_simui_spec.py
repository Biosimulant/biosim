import pytest


@pytest.fixture
def fastapi_client():
    try:  # pragma: no cover - optional dependency path
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi not installed (install with biosim[ui])")
    return FastAPI, TestClient


def _make_world(biosim):
    return biosim.BioWorld()


def test_spec_version_and_modules(biosim, fastapi_client):
    FastAPI, TestClient = fastapi_client
    world = _make_world(biosim)

    class M1(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    class M2(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world.add_biomodule("m1", M1())
    world.add_biomodule("m2", M2())

    ui = biosim.simui.Interface(world)
    app = FastAPI()
    ui.mount(app, "/ui")
    client = TestClient(app)
    r = client.get("/ui/api/spec")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "2"
    assert set(data.get("modules", [])) == {"m1", "m2"}


def test_run_endpoint_accepts_duration(biosim, fastapi_client):
    FastAPI, TestClient = fastapi_client
    world = _make_world(biosim)

    class M1(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world.add_biomodule("m1", M1())

    ui = biosim.simui.Interface(world)
    app = FastAPI()
    ui.mount(app, "/ui")
    client = TestClient(app)
    r = client.post("/ui/api/run", json={"duration": 0.2, "tick_dt": 0.1})
    assert r.status_code in (202, 409)

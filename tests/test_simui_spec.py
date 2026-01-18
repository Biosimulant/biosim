import pytest


@pytest.fixture
def fastapi_client():
    try:  # pragma: no cover - optional dependency path
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("fastapi not installed (install with bsim[ui])")
    return FastAPI, TestClient


def _make_world(bsim, with_temp=False):
    if with_temp:
        solver = bsim.FixedStepBioSolver(temperature=bsim.TemperatureParams(initial=12.5))
    else:
        solver = bsim.FixedStepSolver()
    return bsim.BioWorld(solver=solver)


def test_spec_version_and_modules(bsim, fastapi_client):
    FastAPI, TestClient = fastapi_client
    world = _make_world(bsim)

    class M1(bsim.BioModule):
        pass

    class M2(bsim.BioModule):
        pass

    world.add_biomodule(M1())
    world.add_biomodule(M2())

    ui = bsim.simui.Interface(world)
    app = FastAPI()
    ui.mount(app, "/ui")
    client = TestClient(app)
    r = client.get("/ui/api/spec")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "2"
    assert set(data.get("modules", [])) == {"M1", "M2"}


def test_temperature_control_detection_and_override(bsim, fastapi_client):
    FastAPI, TestClient = fastapi_client
    world = _make_world(bsim, with_temp=True)
    ui = bsim.simui.Interface(world)
    app = FastAPI()
    ui.mount(app, "/ui")
    client = TestClient(app)
    spec = client.get("/ui/api/spec").json()
    ctl_names = [c.get("name") for c in spec.get("controls", []) if c.get("type") == "number"]
    assert "temperature" in ctl_names
    r = client.post("/ui/api/run", json={"steps": 2, "dt": 0.5, "temperature": 33.3})
    assert r.status_code in (202, 409)

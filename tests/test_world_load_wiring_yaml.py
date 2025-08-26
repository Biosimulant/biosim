import pytest
from pathlib import Path


try:  # pragma: no cover - env dependent
    import yaml  # type: ignore
    _HAS_YAML = True
except Exception:  # pragma: no cover
    _HAS_YAML = False


@pytest.mark.skipif(not _HAS_YAML, reason="YAML (pyyaml) not available")
def test_world_load_wiring_yaml_example_file(bsim):
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    world.load_wiring(str(Path("examples/configs/brain.yaml")))
    world.simulate(steps=1, dt=0.1)

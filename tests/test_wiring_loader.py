import io
from pathlib import Path

import pytest

try:  # pragma: no cover - env dependent
    import tomllib  # type: ignore[attr-defined]
    _HAS_TOML = True
except Exception:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
        _HAS_TOML = True
    except Exception:
        _HAS_TOML = False


def _common_modules(bsim):
    from examples.wiring_builder_demo import Eye, LGN, SC
    return Eye, LGN, SC


@pytest.mark.skipif(not _HAS_TOML, reason="TOML support not available")
def test_load_wiring_toml(tmp_path: Path, bsim):
    Eye, LGN, SC = _common_modules(bsim)
    # Build a TOML spec that uses class paths
    content = f"""
[modules.eye]
class = "{Eye.__module__}.{Eye.__name__}"

[modules.lgn]
class = "{LGN.__module__}.{LGN.__name__}"

[modules.sc]
class = "{SC.__module__}.{SC.__name__}"

[[wiring]]
from = "eye.out.visual_stream"
to = ["lgn.in.retina", "sc.in.vision"]
"""
    path = tmp_path / "wiring.toml"
    path.write_text(content)

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    bsim.load_wiring_toml(world, path)
    world.simulate(steps=1, dt=0.1)


def test_build_from_spec_with_preadded_modules(bsim):
    Eye, LGN, SC = _common_modules(bsim)
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    spec = {
        "modules": {
            "eye": {"class": f"{Eye.__module__}.{Eye.__name__}"},
            "lgn": {"class": f"{LGN.__module__}.{LGN.__name__}"},
            "sc": {"class": f"{SC.__module__}.{SC.__name__}"},
        },
        "wiring": [
            {"from": "eye.out.visual_stream", "to": ["lgn.in.retina"]},
            {"from": "lgn.out.thalamus", "to": ["sc.in.vision"]},
        ],
    }
    bsim.build_from_spec(world, spec)
    world.simulate(steps=1, dt=0.1)

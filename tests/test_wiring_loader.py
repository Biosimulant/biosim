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


def _common_modules(biosim):
    from examples.wiring_builder_demo import Eye, LGN, SC
    return Eye, LGN, SC


@pytest.mark.skipif(not _HAS_TOML, reason="TOML support not available")
def test_load_wiring_toml(tmp_path: Path, biosim):
    Eye, LGN, SC = _common_modules(biosim)
    content = f"""
[modules.eye]
class = "{Eye.__module__}.{Eye.__name__}"
min_dt = 0.1

[modules.lgn]
class = "{LGN.__module__}.{LGN.__name__}"
min_dt = 0.1

[modules.sc]
class = "{SC.__module__}.{SC.__name__}"
min_dt = 0.1

[[wiring]]
from = "eye.visual_stream"
to = ["lgn.retina", "sc.vision"]
"""
    path = tmp_path / "wiring.toml"
    path.write_text(content)

    world = biosim.BioWorld()
    biosim.load_wiring_toml(world, path)
    world.run(duration=0.1, tick_dt=0.1)


def test_build_from_spec_with_preadded_modules(biosim):
    Eye, LGN, SC = _common_modules(biosim)
    world = biosim.BioWorld()
    spec = {
        "modules": {
            "eye": {"class": f"{Eye.__module__}.{Eye.__name__}", "min_dt": 0.1},
            "lgn": {"class": f"{LGN.__module__}.{LGN.__name__}", "min_dt": 0.1},
            "sc": {"class": f"{SC.__module__}.{SC.__name__}", "min_dt": 0.1},
        },
        "wiring": [
            {"from": "eye.visual_stream", "to": ["lgn.retina"]},
            {"from": "lgn.thalamus", "to": ["sc.vision"]},
        ],
    }
    biosim.build_from_spec(world, spec)
    world.run(duration=0.1, tick_dt=0.1)

# API: BioWorld and BioWorldEvent

BioWorld orchestrates simulation steps, emits lifecycle events, and routes directed biosignals between modules.

Class signature
```python
@dataclass
class BioWorld:
    solver: bsim.Solver
    listeners: list[Listener] = []
    # internal
    _biomodule_listeners: dict[BioModule, Listener]
    _signal_routes: dict[tuple[BioModule, str], list[BioModule]]
    _loaded_emitted: bool
```

Typical values during a run
- `solver` → `FixedStepSolver()`
- `listeners` → `[<function print_listener>, <module_listener>, ...]`
- `_biomodule_listeners` → `{ Eye(): <listener>, LGN(): <listener> }`
- `_signal_routes` → `{ (Eye(), 'visual_stream'): [LGN()], (LGN(), 'thalamus'): [SC()] }`
- After first `simulate`: `_loaded_emitted` → `True`

Lifecycle
- Emits: `LOADED` (once), `BEFORE_SIMULATION`, `STEP`×N, `AFTER_SIMULATION`.
- Exceptions in listeners/handlers are logged and ignored.

Key methods
- `on(listener)` / `off(listener)`
- `add_biomodule(module)` / `remove_biomodule(module)`
- `connect_biomodules(src, topic, dst)` / `disconnect_biomodules(src, topic, dst)`
- `publish_biosignal(src, topic, payload)`
- `simulate(steps: int, dt: float) -> dict`: returns `{"steps": int, "time": float}` for `FixedStepSolver`.
- `load_wiring(path: str)` → YAML/TOML loader
- `describe_wiring() -> list[tuple[str, str, str]]`

Example
```python
world = bsim.BioWorld(solver=bsim.FixedStepSolver())
world.on(lambda ev, p: print(ev.name, p))
eye, lgn = Eye(), LGN()
world.add_biomodule(eye)
world.add_biomodule(lgn)
world.connect_biomodules(eye, 'visual_stream', lgn)
print(world.describe_wiring())
print(world.simulate(steps=2, dt=0.1))
```

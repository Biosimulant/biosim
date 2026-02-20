# API: BioWorld and WorldEvent

BioWorld orchestrates runnable biomodules, emits lifecycle events, and routes biosignals between modules.

Class signature
```python
class BioWorld:
    def __init__(self, *, time_unit: str = "seconds") -> None: ...
```

Lifecycle
- Emits: `STARTED`, `TICK`, `FINISHED`.
- May also emit: `PAUSED`, `RESUMED`, `STOPPED`, `ERROR`.
- Exceptions in listeners are logged and do not stop the world.

Key methods
- `on(listener)` / `off(listener)`
- `add_biomodule(name, module, min_dt=None, priority=0)`
- `connect("src.port", "dst.port")`
- `setup(config=None)`
- `run(duration: float, tick_dt: Optional[float] = None)`
- `request_pause()` / `request_resume()` / `request_stop()`
- `current_time()`
- `module_names`
- `get_outputs(name)`
- `collect_visuals()`

Example
```python
world = biosim.BioWorld()
world.on(lambda ev, p: print(ev.value, p))

eye, lgn = Eye(), LGN()
world.add_biomodule("eye", eye)
world.add_biomodule("lgn", lgn)
world.connect("eye.visual_stream", "lgn.retina")
world.run(duration=0.2, tick_dt=0.1)
```

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
- Event payloads now include additive progress fields during active runs:
  `start`, `end`, `duration`, `progress`, `progress_pct`, `remaining`.

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

Priority semantics
- Modules are always scheduled by due time first.
- If multiple modules are due at the same simulation time, higher `priority` values run earlier.

Signal store semantics
- The world keeps the latest non-empty output mapping for each module in an internal signal store.
- A non-empty `get_outputs()` result replaces that module's previously stored outputs.
- Returning `{}` or `None` does not clear previously stored outputs.
- If a replacement mapping omits a previously published port, that omitted port disappears from the store.
- The store is reset by `setup()`.
- If a consumer reads a state-like signal older than its own `min_dt`, the world logs a stale-read warning once for that source timestamp.
- Event signals still persist in the store, but downstream delivery is de-duplicated per connection using the signal timestamp.

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

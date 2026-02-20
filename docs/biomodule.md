# API: BioModule

BioModule encapsulates behavior with local state. It:
- Implements a runnable contract (`setup/reset/advance_to/...`).
- Receives inputs via `set_inputs(...)` and emits outputs via `get_outputs()`.
- Optionally declares connection ports for validation via `inputs()` and `outputs()`.

Signature (selected)
```python
class BioModule:
    min_dt: float  # required positive value (seconds by default), defaults to 0.0

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None: ...
    def reset(self) -> None: ...
    def advance_to(self, t: float) -> None: ...       # abstract
    def set_inputs(self, signals: Dict[str, BioSignal]) -> None: ...
    def get_outputs(self) -> Dict[str, BioSignal]: ... # abstract
    def get_state(self) -> Dict[str, Any]: ...
    def next_due_time(self, now: float) -> float: ...  # returns now + min_dt by default
    def inputs(self) -> Set[str]: ...
    def outputs(self) -> Set[str]: ...
    def input_schemas(self) -> Dict[str, Any]: ...     # optional, for future tooling
    def output_schemas(self) -> Dict[str, Any]: ...    # optional, for future tooling
    def visualize(self) -> Optional[VisualSpec | List[VisualSpec]]: ...
```

Notes:
- `advance_to` and `get_outputs` are abstract (must be implemented).
- `setup` receives an optional config dict (per-module section from the world config), not the BioWorld instance.
- `next_due_time` returns `float` (not Optional); default implementation is `now + min_dt`.
- `input_schemas`/`output_schemas` return port-name-to-schema mappings; currently unused but reserved for future validation.
- `visualize` returns a VisualSpec dict or list of dicts for browser rendering (see README VisualSpec types).

Example with local state
```python
class Eye(biosim.BioModule):
    min_dt = 0.01

    def __init__(self):
        self.photons_seen = 0

    def outputs(self):
        return {"visual_stream"}

    def advance_to(self, t: float) -> None:
        self.photons_seen += 1

    def get_outputs(self):
        source = getattr(self, "_world_name", "eye")
        return {
            "visual_stream": biosim.BioSignal(
                source=source,
                name="visual_stream",
                value={"count": self.photons_seen},
                time=0.0,
                metadata=biosim.SignalMetadata(units="1"),
            )
        }
```

Typical values at runtime
- `t` -> current world time (float)
- `self.photons_seen` after two ticks -> `2`

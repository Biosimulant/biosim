# API: BioModule

BioModule encapsulates behavior with local state. It can:
- Listen to global world events via `on_event` and optional `subscriptions()`.
- Exchange directed messages via `on_signal` and `publish_biosignal` on the world.
- Optionally declare connection ports for validation via `inputs()` and `outputs()`.

Signature (selected)
```python
class BioModule:
    def subscriptions(self) -> set[BioWorldEvent]: ...  # empty → all
    def on_event(self, event, payload: dict, world: BioWorld) -> None: ...
    def on_signal(self, topic: str, payload: dict, source: BioModule, world: BioWorld) -> None: ...
    def inputs(self) -> set[str]: ...      # optional validation
    def outputs(self) -> set[str]: ...     # optional validation
```

Example with local state
```python
class Eye(bsim.BioModule):
    def __init__(self):
        self.photons_seen = 0
    def subscriptions(self):
        return {bsim.BioWorldEvent.STEP}
    def outputs(self):
        return {"visual_stream"}
    def on_event(self, event, payload, world):
        self.photons_seen += 1
        world.publish_biosignal(self, "visual_stream", {"t": payload.get("t")})
```

Typical values at runtime
- `event` → `BioWorldEvent.STEP`
- `payload` (from FixedStepSolver) → `{ 'i': 0, 't': 0.1 }`
- `self.photons_seen` after two steps → `2`

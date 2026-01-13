# Plugin Architecture Implementation Plan

## Goal

Enable users to:
1. Run simulations entirely from YAML configs
2. Create custom solvers/modules in Python packages
3. Publish packages that others can reference in YAML

## Current State

### What Works
- Modules can be referenced by dotted path: `class: my_package.MyModule`
- `load_wiring()` dynamically imports classes via `_import_from_string()`
- YAML configs can define modules and wiring

### What's Missing
- Custom solvers cannot be declared in YAML (only `fixed` or `default` strings)
- No documentation/template for creating publishable packs
- No standard pattern for solver parameters in YAML

---

## Phase 1: Custom Solver Support in YAML

### Changes Required

#### 1.1 Update `__main__.py` - `create_world()` function

Current:
```python
solver_type = meta.get("solver", "fixed")
if solver_type == "default":
    # hardcoded DefaultBioSolver
else:
    # hardcoded FixedStepSolver
```

New behavior - support three formats:

```yaml
# Format 1: String shorthand (existing)
meta:
  solver: fixed  # or "default"

# Format 2: Built-in solver with parameters
meta:
  solver:
    type: default
    temperature:
      initial: 20.0
      bounds: [0.0, 50.0]

# Format 3: Custom solver class
meta:
  solver:
    class: my_package.MySolver
    args:
      custom_param: 42
```

#### 1.2 Implementation Logic

```python
def create_solver(solver_spec: Any) -> Solver:
    """Create solver from YAML spec."""
    import bsim
    from bsim.wiring import _import_from_string

    # Format 1: String shorthand
    if isinstance(solver_spec, str):
        if solver_spec == "default":
            return bsim.DefaultBioSolver()
        return bsim.FixedStepSolver()

    # Format 2 & 3: Dict with type or class
    if isinstance(solver_spec, dict):
        # Custom class
        if "class" in solver_spec:
            cls = _import_from_string(solver_spec["class"])
            args = solver_spec.get("args", {})
            return cls(**args)

        # Built-in with parameters
        solver_type = solver_spec.get("type", "fixed")
        if solver_type == "default":
            temp_spec = solver_spec.get("temperature", {})
            if isinstance(temp_spec, dict):
                from bsim.solver import TemperatureParams
                temp_params = TemperatureParams(
                    initial=temp_spec.get("initial", 25.0),
                    bounds=tuple(temp_spec.get("bounds", (0.0, 50.0))),
                )
                return bsim.DefaultBioSolver(temperature=temp_params)
            return bsim.DefaultBioSolver()
        return bsim.FixedStepSolver()

    # Fallback
    return bsim.FixedStepSolver()
```

#### 1.3 Files to Modify

| File | Changes |
|------|---------|
| `src/bsim/__main__.py` | Update `create_world()` to use `create_solver()` |
| `src/bsim/wiring.py` | Export `_import_from_string` (make public) |

---

## Phase 2: Module Protocol Documentation

### 2.1 BioModule Protocol

Document the duck-typing protocol that custom modules must implement:

```python
class BioModule(Protocol):
    """Protocol for simulation modules."""

    def subscriptions(self) -> Set[BioWorldEvent]:
        """Events this module listens to (STEP, etc.)."""
        ...

    def inputs(self) -> Set[str]:
        """Input port names this module accepts."""
        ...

    def outputs(self) -> Set[str]:
        """Output port names this module emits."""
        ...

    def reset(self) -> None:
        """Reset state for new simulation run."""
        ...

    def on_event(self, event: BioWorldEvent, payload: Dict, world: BioWorld) -> None:
        """Handle world events (called on each STEP)."""
        ...

    def on_signal(self, topic: str, payload: Dict, source: Any, world: BioWorld) -> None:
        """Handle incoming signals from connected modules."""
        ...

    def visualize(self) -> Optional[VisualSpec]:
        """Return visualization data (optional)."""
        ...
```

### 2.2 Solver Protocol

```python
class Solver(Protocol):
    """Protocol for custom solvers."""

    def step(self, state: Dict, dt: float) -> Dict:
        """Advance state by one timestep."""
        ...

    def with_overrides(self, overrides: Dict) -> Solver:
        """Return new solver with parameter overrides (for UI control)."""
        ...
```

---

## Phase 3: Publishable Pack Template

### 3.1 Recommended Package Structure

```
my-bsim-pack/
├── pyproject.toml
├── README.md
├── src/
│   └── my_pack/
│       ├── __init__.py       # Export all public classes
│       ├── modules.py        # BioModule implementations
│       ├── solvers.py        # Custom Solver implementations (optional)
│       └── presets.py        # Parameter presets (optional)
├── examples/
│   └── demo.yaml             # Example config using this pack
└── tests/
    └── test_modules.py
```

### 3.2 Minimal pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "bsim-my-pack"
version = "0.1.0"
description = "Custom modules for bsim"
dependencies = ["bsim>=0.1.0"]

[project.optional-dependencies]
dev = ["pytest", "bsim[ui]"]
```

### 3.3 Example __init__.py

```python
"""My custom bsim pack."""
from .modules import MyNeuron, MySynapse
from .solvers import AdaptiveSolver

__all__ = ["MyNeuron", "MySynapse", "AdaptiveSolver"]
```

---

## Phase 4: Entry Points Discovery (Future)

### 4.1 Registration via Entry Points

```toml
# pyproject.toml
[project.entry-points."bsim.packs"]
my_pack = "my_pack"
```

### 4.2 Short Name Resolution

```yaml
# Instead of:
modules:
  neuron:
    class: my_pack.modules.MyNeuron

# Could use:
modules:
  neuron:
    class: my_pack:MyNeuron  # Short form with colon
```

### 4.3 Implementation

```python
def resolve_class_path(path: str) -> type:
    """Resolve class from dotted path or short form."""
    if ":" in path:
        # Short form: pack_name:ClassName
        pack_name, class_name = path.split(":", 1)
        # Look up entry point
        from importlib.metadata import entry_points
        eps = entry_points(group="bsim.packs")
        for ep in eps:
            if ep.name == pack_name:
                module = ep.load()
                return getattr(module, class_name)
        raise ValueError(f"Pack not found: {pack_name}")
    # Standard dotted path
    return _import_from_string(path)
```

---

## Implementation Order

### Immediate (Phase 1)
1. Update `__main__.py` with `create_solver()` function
2. Support dict-based solver spec in YAML
3. Test with custom solver class

### Short-term (Phase 2-3)
4. Document BioModule and Solver protocols
5. Create example external pack structure
6. Add validation for custom classes

### Future (Phase 4)
7. Entry points discovery system
8. Short name resolution
9. Pack registry/listing command

---

## Example: Complete YAML with Custom Solver

```yaml
# config.yaml - uses custom solver from external package
meta:
  title: "Advanced Neural Simulation"
  description: |
    Using custom adaptive solver from neurolab package.
  solver:
    class: bsim_neurolab.AdaptiveSolver
    args:
      tolerance: 1e-6
      max_substeps: 10

modules:
  input:
    class: bsim.packs.neuro.PoissonInput
    args:
      n: 100
      rate_hz: 15.0

  neuron:
    class: bsim_neurolab.HodgkinHuxley
    args:
      conductance_na: 120.0
      conductance_k: 36.0

  monitor:
    class: bsim.packs.neuro.SpikeMonitor
    args:
      max_spikes: 10000

wiring:
  - from: input.out.spikes
    to: [neuron.in.spikes]
  - from: neuron.out.spikes
    to: [monitor.in.spikes]
```

---

## Acceptance Criteria

### Phase 1 Complete When:
- [ ] `python -m bsim config.yaml` works with `solver.class` in meta
- [ ] Custom solver receives args from YAML
- [ ] Built-in solvers still work with string shorthand
- [ ] Error messages are clear for import failures

### Phase 2-3 Complete When:
- [ ] Protocol documentation exists
- [ ] Example external pack can be pip installed
- [ ] Example pack's classes work in YAML configs

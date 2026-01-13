# Plugin Development Guide

This guide explains how to create custom modules and solvers for bsim that can be:
1. Used in your own projects
2. Published as pip-installable packages
3. Referenced in YAML configs by other users

## Quick Start

```bash
# Install bsim
pip install bsim

# Create your package
mkdir my-bsim-pack && cd my-bsim-pack
# ... implement modules ...

# Use in YAML
# config.yaml
modules:
  my_module:
    class: my_pack.MyModule
```

---

## Part 1: Creating Custom Modules

### The BioModule Protocol

All modules must implement the `BioModule` interface. Here's the complete protocol:

```python
from abc import ABC
from typing import Any, Dict, Set, Optional, List
from bsim import BioWorld, BioWorldEvent
from bsim.visuals import VisualSpec

class BioModule(ABC):
    """Base interface for simulation modules."""

    def subscriptions(self) -> Set[BioWorldEvent]:
        """Which world events to receive. Empty set = all events."""
        return set()  # Default: receive all

    def on_event(
        self,
        event: BioWorldEvent,
        payload: Dict[str, Any],
        world: BioWorld
    ) -> None:
        """Handle world events (STEP, etc.)."""
        pass

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: "BioModule",
        world: BioWorld
    ) -> None:
        """Handle signals from connected modules."""
        pass

    def inputs(self) -> Set[str]:
        """Declare input port names for validation."""
        return set()

    def outputs(self) -> Set[str]:
        """Declare output port names for validation."""
        return set()

    def reset(self) -> None:
        """Reset state for new simulation run (optional)."""
        pass

    def visualize(self) -> Optional[VisualSpec | List[VisualSpec]]:
        """Return visualization data (optional)."""
        return None
```

### Minimal Module Example

```python
# my_pack/modules.py
from typing import Any, Dict, Set
from bsim import BioModule, BioWorld, BioWorldEvent

class Counter(BioModule):
    """Counts simulation steps and emits count."""

    def __init__(self, name: str = "counter"):
        self.name = name
        self._count = 0

    def subscriptions(self) -> Set[BioWorldEvent]:
        return {BioWorldEvent.STEP}

    def inputs(self) -> Set[str]:
        return set()  # No inputs

    def outputs(self) -> Set[str]:
        return {"count"}

    def reset(self) -> None:
        self._count = 0

    def on_event(
        self,
        event: BioWorldEvent,
        payload: Dict[str, Any],
        world: BioWorld
    ) -> None:
        if event == BioWorldEvent.STEP:
            self._count += 1
            world.publish_biosignal(
                self,
                topic="count",
                payload={"count": self._count, "t": payload.get("t")}
            )

    def visualize(self):
        return {
            "render": "metric",
            "data": {"value": self._count, "label": f"{self.name} count"}
        }
```

### Module with Signal Handling

```python
class Accumulator(BioModule):
    """Receives values and accumulates them."""

    def __init__(self, initial: float = 0.0):
        self._total = initial
        self._initial = initial

    def inputs(self) -> Set[str]:
        return {"value"}  # Accepts 'value' signals

    def outputs(self) -> Set[str]:
        return {"total"}

    def reset(self) -> None:
        self._total = self._initial

    def on_signal(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: Any,
        world: BioWorld
    ) -> None:
        if topic == "value":
            self._total += payload.get("amount", 0)
            world.publish_biosignal(
                self,
                topic="total",
                payload={"total": self._total}
            )
```

---

## Part 2: Creating Custom Solvers

### The Solver Protocol

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Mapping
from bsim import BioWorldEvent

class Solver(ABC):
    """Base interface for simulation solvers."""

    @abstractmethod
    def simulate(
        self,
        *,
        steps: int,
        dt: float,
        emit: Callable[[BioWorldEvent, Dict[str, Any]], None],
    ) -> Any:
        """Run simulation for given steps.

        Args:
            steps: Number of simulation steps
            dt: Time step size
            emit: Callback to emit events (call with BioWorldEvent.STEP)

        Returns:
            Final state dict (typically {"time": float, "steps": int, ...})
        """
        raise NotImplementedError

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Solver":
        """Return solver with parameter overrides (for UI control).

        Default returns self (no overrides supported).
        """
        return self
```

### Minimal Solver Example

```python
# my_pack/solvers.py
from typing import Any, Callable, Dict, Mapping
from bsim import Solver, BioWorldEvent

class VariableStepSolver(Solver):
    """Solver with adaptive time stepping."""

    def __init__(self, min_dt: float = 0.001, max_dt: float = 0.1):
        self.min_dt = min_dt
        self.max_dt = max_dt
        self._current_dt = max_dt

    def simulate(
        self,
        *,
        steps: int,
        dt: float,  # Base dt, may be adapted
        emit: Callable[[BioWorldEvent, Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        time = 0.0
        actual_dt = min(dt, self.max_dt)

        for i in range(steps):
            time += actual_dt
            emit(BioWorldEvent.STEP, {
                "i": i,
                "t": time,
                "dt": actual_dt
            })

        return {"time": time, "steps": steps}

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Solver":
        # Support overriding max_dt from UI
        if "max_dt" in overrides:
            return VariableStepSolver(
                min_dt=self.min_dt,
                max_dt=float(overrides["max_dt"])
            )
        return self
```

### Solver with State Management

```python
from dataclasses import dataclass, replace

@dataclass
class AdaptiveParams:
    tolerance: float = 1e-6
    max_substeps: int = 10

class AdaptiveSolver(Solver):
    """Solver with error-controlled time stepping."""

    def __init__(self, params: AdaptiveParams = None):
        self.params = params or AdaptiveParams()
        self._state: Dict[str, float] = {}

    def simulate(
        self,
        *,
        steps: int,
        dt: float,
        emit: Callable[[BioWorldEvent, Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        time = 0.0

        for i in range(steps):
            # Adaptive substeps based on tolerance
            substeps = self._compute_substeps(dt)
            sub_dt = dt / substeps

            for _ in range(substeps):
                time += sub_dt

            emit(BioWorldEvent.STEP, {
                "i": i,
                "t": time,
                "substeps": substeps
            })

        return {"time": time, "steps": steps}

    def _compute_substeps(self, dt: float) -> int:
        # Simplified: in practice, use error estimation
        return min(self.params.max_substeps, max(1, int(dt / 0.01)))

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Solver":
        if "tolerance" in overrides:
            new_params = replace(
                self.params,
                tolerance=float(overrides["tolerance"])
            )
            return AdaptiveSolver(params=new_params)
        return self
```

---

## Part 3: Visualization Specs

Modules can return visualization data in these formats:

### Timeseries

```python
def visualize(self):
    return {
        "render": "timeseries",
        "data": {
            "series": [
                {"name": "value_a", "points": [[0, 1], [1, 2], [2, 3]]},
                {"name": "value_b", "points": [[0, 0], [1, 1], [2, 4]]},
            ],
            "title": "My Timeseries"
        }
    }
```

### Table

```python
def visualize(self):
    return {
        "render": "table",
        "data": {
            "columns": ["Name", "Value", "Unit"],
            "rows": [
                ["Temperature", "25.0", "°C"],
                ["Pressure", "101.3", "kPa"],
            ],
            "title": "Parameters"
        }
    }
```

### Metric

```python
def visualize(self):
    return {
        "render": "metric",
        "data": {
            "value": 42,
            "label": "Count",
            "unit": "items"
        }
    }
```

### Image (SVG)

```python
def visualize(self):
    return {
        "render": "image",
        "data": {
            "svg": "<svg>...</svg>",
            "title": "Phase Space"
        }
    }
```

---

## Part 4: Package Structure

### Recommended Layout

```
my-bsim-pack/
├── pyproject.toml          # Package metadata
├── README.md               # Documentation
├── src/
│   └── my_pack/
│       ├── __init__.py     # Public exports
│       ├── modules.py      # BioModule implementations
│       ├── solvers.py      # Solver implementations (optional)
│       └── presets.py      # Parameter presets (optional)
├── examples/
│   └── demo.yaml           # Example config
└── tests/
    ├── test_modules.py
    └── test_solvers.py
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "bsim-my-pack"
version = "0.1.0"
description = "Custom modules for bsim simulations"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "bsim>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "bsim[ui]",
]

[tool.hatch.build.targets.wheel]
packages = ["src/my_pack"]
```

### __init__.py

```python
"""My custom bsim pack."""
from .modules import Counter, Accumulator, MyNeuron
from .solvers import AdaptiveSolver

__all__ = [
    "Counter",
    "Accumulator",
    "MyNeuron",
    "AdaptiveSolver",
]
```

---

## Part 5: Using in YAML Configs

Once published (`pip install bsim-my-pack`), users reference your classes:

```yaml
# config.yaml
meta:
  title: "Using My Pack"
  solver:
    class: my_pack.AdaptiveSolver
    args:
      tolerance: 1e-8

modules:
  counter:
    class: my_pack.Counter
    args:
      name: "step_counter"

  accumulator:
    class: my_pack.Accumulator
    args:
      initial: 0.0

wiring:
  - from: counter.out.count
    to: [accumulator.in.value]
```

Run with:

```bash
python -m bsim config.yaml --simui
```

---

## Part 6: Testing Your Pack

### Unit Tests

```python
# tests/test_modules.py
import pytest
from my_pack import Counter

def test_counter_increments():
    counter = Counter()
    counter.reset()

    # Simulate receiving STEP events
    from bsim import BioWorldEvent

    class MockWorld:
        def __init__(self):
            self.signals = []

        def publish_biosignal(self, source, topic, payload):
            self.signals.append((topic, payload))

    world = MockWorld()
    counter.on_event(BioWorldEvent.STEP, {"t": 0.1}, world)
    counter.on_event(BioWorldEvent.STEP, {"t": 0.2}, world)

    assert len(world.signals) == 2
    assert world.signals[1][1]["count"] == 2
```

### Integration Tests

```python
# tests/test_integration.py
import bsim
from my_pack import Counter

def test_counter_in_world():
    world = bsim.BioWorld()
    counter = Counter()
    world.add_biomodule(counter)

    world.simulate(steps=10, dt=0.1)

    vis = counter.visualize()
    assert vis["data"]["value"] == 10
```

---

## Summary

| Component | Base Class | Key Methods |
|-----------|------------|-------------|
| Module | `BioModule` | `on_event()`, `on_signal()`, `inputs()`, `outputs()`, `visualize()` |
| Solver | `Solver` | `simulate()`, `with_overrides()` |
| Process | `Process` | `init_state()`, `update()` |

Your custom modules and solvers can be:
1. Used directly in Python
2. Referenced by class path in YAML configs
3. Published as pip packages for the community

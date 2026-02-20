# Plugin Development Guide

This guide explains how to create custom biomodules for biosim that can be:
1. Used in your own projects
2. Published as pip-installable packages
3. Referenced in YAML configs by other users

## Quick Start

```bash
# Install biosim
pip install biosim

# Create your package
mkdir my-biosim-pack && cd my-biosim-pack
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

All modules implement the runnable contract. A minimal interface looks like:

```python
from typing import Any, Dict, List, Optional, Set
from biosim import BioModule, BioSignal, SignalMetadata

class BioModule:
    min_dt: float  # required positive value

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None: ...
    def reset(self) -> None: ...
    def advance_to(self, t: float) -> None: ...       # abstract
    def set_inputs(self, signals: Dict[str, BioSignal]) -> None: ...
    def get_outputs(self) -> Dict[str, BioSignal]: ... # abstract
    def get_state(self) -> Dict[str, Any]: ...
    def next_due_time(self, now: float) -> float: ...  # returns now + min_dt by default
    def inputs(self) -> Set[str]: ...
    def outputs(self) -> Set[str]: ...
    def visualize(self) -> Optional[Dict | List[Dict]]: ...
```

### Minimal Module Example

```python
# my_pack/modules.py
from typing import Dict, Set
from biosim import BioModule, BioSignal, SignalMetadata

class Counter(BioModule):
    """Counts ticks and emits a count signal."""

    min_dt = 0.1

    def __init__(self, name: str = "counter"):
        self.name = name
        self._count = 0
        self._time = 0.0

    def outputs(self) -> Set[str]:
        return {"count"}

    def reset(self) -> None:
        self._count = 0
        self._time = 0.0

    def advance_to(self, t: float) -> None:
        self._count += 1
        self._time = t

    def get_outputs(self) -> Dict[str, BioSignal]:
        source = getattr(self, "_world_name", "counter")
        return {
            "count": BioSignal(
                source=source,
                name="count",
                value={"count": self._count},
                time=self._time,
                metadata=SignalMetadata(units="1"),
            )
        }
```

### Module With Inputs

```python
class Accumulator(BioModule):
    min_dt = 0.1

    def __init__(self):
        self._total = 0
        self._inputs = {}

    def inputs(self):
        return {"value"}

    def set_inputs(self, inputs):
        self._inputs = inputs

    def advance_to(self, t: float) -> None:
        if "value" in self._inputs:
            self._total += self._inputs["value"].value

    def get_outputs(self):
        source = getattr(self, "_world_name", "accumulator")
        return {
            "sum": BioSignal(
                source=source,
                name="sum",
                value=self._total,
                time=0.0,
                metadata=SignalMetadata(units="1"),
            )
        }
```

---

## Part 2: Packaging and Distribution

### Package layout

```
my-biosim-pack/
├── pyproject.toml
├── src/
│   └── my_pack/
│       ├── __init__.py
│       └── modules.py
└── tests/
    └── test_modules.py
```

### Export module classes

```python
# my_pack/__init__.py
from .modules import Counter, Accumulator

__all__ = ["Counter", "Accumulator"]
```

### Use in YAML configs

```yaml
modules:
  counter:
    class: my_pack.Counter
    args:
      name: "demo"
  accumulator:
    class: my_pack.Accumulator
wiring:
  - { from: counter.count, to: [accumulator.value] }
```

---

## Part 3: Testing

Use pytest to validate your module behavior and signal outputs.

```python
def test_counter_emits():
    m = Counter()
    m.advance_to(0.1)
    out = m.get_outputs()
    assert "count" in out
```

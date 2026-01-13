# bsim-my-pack

A template for creating custom bsim module packs.

## Installation

```bash
# Development install
pip install -e .

# Or install from PyPI (after publishing)
pip install bsim-my-pack
```

## Usage

### In Python

```python
import bsim
from my_pack import Counter, VariableStepSolver

world = bsim.BioWorld(solver=VariableStepSolver(max_dt=0.05))
world.add_biomodule(Counter(name="my_counter"))
world.simulate(steps=100, dt=0.1)
```

### In YAML Configs

```yaml
meta:
  solver:
    class: my_pack.VariableStepSolver
    args:
      max_dt: 0.05

modules:
  counter:
    class: my_pack.Counter
    args:
      name: "my_counter"
```

Run with:
```bash
python -m bsim config.yaml --simui
```

## Included Components

### Modules

| Module | Description | Inputs | Outputs |
|--------|-------------|--------|---------|
| `Counter` | Counts simulation steps | - | `count` |
| `Accumulator` | Accumulates values | `value` | `total` |
| `SignalLogger` | Logs signals for debugging | any | - |

### Solvers

| Solver | Description | Parameters |
|--------|-------------|------------|
| `VariableStepSolver` | Configurable dt bounds | `min_dt`, `max_dt` |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run example
python -m bsim examples/demo.yaml --simui
```

## Creating Your Own Pack

1. Copy this template
2. Rename `my_pack` to your package name
3. Update `pyproject.toml` with your details
4. Implement your modules in `modules.py`
5. Implement custom solvers in `solvers.py` (optional)
6. Add example configs in `examples/`
7. Publish to PyPI

## License

MIT

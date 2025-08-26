# API: Solver and FixedStepSolver

Solvers drive the simulation by advancing time and emitting events. They are injected into `BioWorld`.

Protocol
```python
class Solver(abc.ABC):
    def simulate(*, steps: int, dt: float,
                 emit: Callable[[BioWorldEvent, dict], None]) -> Any: ...
```

Built-in solver: FixedStepSolver
```python
result = FixedStepSolver().simulate(
    steps=3,
    dt=0.1,
    emit=lambda ev, p: print(ev, p),
)
# Emits STEP events:
# (STEP, {'i': 0, 't': 0.1})
# (STEP, {'i': 1, 't': 0.2})
# (STEP, {'i': 2, 't': 0.3})
# Returns a dict summary:
# {'time': 0.30000000000000004, 'steps': 3}
```

Typical values
- Input: `steps=3`, `dt=0.1`
- Emitted payloads: `{ 'i': 0, 't': 0.1 }`, `{ 'i': 1, 't': 0.2 }`, ...
- Return value: `{ 'time': 0.3, 'steps': 3 }` (minor FP rounding possible)

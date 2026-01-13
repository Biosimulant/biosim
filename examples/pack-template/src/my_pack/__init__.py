"""My custom bsim pack.

This pack provides custom modules and solvers for bsim simulations.

Usage in YAML configs:
    modules:
      counter:
        class: my_pack.Counter
        args:
          name: "my_counter"

    meta:
      solver:
        class: my_pack.VariableStepSolver
        args:
          max_dt: 0.05
"""
from .modules import Counter, Accumulator, SignalLogger
from .solvers import VariableStepSolver

__version__ = "0.1.0"

__all__ = [
    "Counter",
    "Accumulator",
    "SignalLogger",
    "VariableStepSolver",
]

"""
bsim.adapters - Adapter layer for external simulators and ML models.

This module provides adapters that wrap external simulation tools (tellurium, pyNeuroML, etc.)
and ML inference engines (ONNX) to work seamlessly within bsim's composition framework.

Example usage:
    from bsim.adapters import TelluriumAdapter, MLAdapter, BioSignal

    # Run an SBML model
    adapter = TelluriumAdapter("model.xml", expose=["glucose", "ATP"])

    # Run an ML model in a simulation loop
    ml = MLAdapter("predictor.onnx", inputs={"x": "input"}, outputs={"y": "prediction"})
"""

from bsim.adapters.base import SimulatorAdapter, AdapterConfig
from bsim.adapters.signals import BioSignal, SignalMetadata
from bsim.adapters.broker import TimeBroker, AdaptiveTimeBroker, TimeScale

__all__ = [
    "SimulatorAdapter",
    "AdapterConfig",
    "BioSignal",
    "SignalMetadata",
    "TimeBroker",
    "AdaptiveTimeBroker",
    "TimeScale",
]

# Lazy imports for optional adapters
def __getattr__(name: str):
    if name == "TelluriumAdapter":
        from bsim.adapters.tellurium import TelluriumAdapter
        return TelluriumAdapter
    elif name == "MLAdapter":
        from bsim.adapters.ml import MLAdapter
        return MLAdapter
    elif name == "NeuroMLAdapter":
        from bsim.adapters.neuroml import NeuroMLAdapter
        return NeuroMLAdapter
    elif name == "NeuroMLNetworkAdapter":
        from bsim.adapters.neuroml import NeuroMLNetworkAdapter
        return NeuroMLNetworkAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""
SimulatorAdapter - Base protocol for wrapping external simulators.

All adapters (tellurium, pyNeuroML, ONNX, etc.) implement this protocol
to integrate with bsim's composition and wiring system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from bsim.adapters.signals import BioSignal


@dataclass
class AdapterConfig:
    """
    Configuration for an adapter instance.

    This is passed to adapters when they're instantiated from a wiring config.
    """

    adapter_type: str
    """Type of adapter (e.g., 'tellurium', 'ml', 'neuroml')."""

    model_path: str | None = None
    """Path to the model file (SBML, ONNX, NeuroML, etc.)."""

    expose: list[str] = field(default_factory=list)
    """List of variables/outputs to expose as BioSignals."""

    parameters: dict[str, Any] = field(default_factory=dict)
    """Parameter overrides for the model."""

    inputs: dict[str, str] = field(default_factory=dict)
    """Mapping of input signal names to model input names."""

    outputs: dict[str, str] = field(default_factory=dict)
    """Mapping of model output names to output signal names."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Additional adapter-specific configuration."""


@runtime_checkable
class SimulatorAdapter(Protocol):
    """
    Protocol defining the interface for simulator adapters.

    Adapters wrap external simulation tools (tellurium, pyNeuroML, ONNX, etc.)
    to work within bsim's composition framework. They handle:
    - Loading and initializing models
    - Advancing simulation state through time
    - Exchanging data via BioSignals
    - Checkpointing and reset

    Lifecycle:
        1. __init__() - Create adapter with config
        2. setup() - Initialize the underlying simulator
        3. Loop:
           a. set_inputs() - Receive signals from other modules
           b. advance_to() - Advance to next sync point
           c. get_outputs() - Emit signals to other modules
        4. reset() - Return to initial state (optional)

    Example implementation:
        class MyAdapter:
            def setup(self, config: dict) -> None:
                self.model = load_model(config["path"])

            def advance_to(self, t: float) -> None:
                self.model.simulate(self.current_time, t)
                self.current_time = t

            def get_outputs(self) -> dict[str, BioSignal]:
                return {"x": BioSignal("my_adapter", "x", self.model.x, self.current_time)}

            def set_inputs(self, signals: dict[str, BioSignal]) -> None:
                for name, signal in signals.items():
                    setattr(self.model, name, signal.value)
    """

    def setup(self, config: dict[str, Any]) -> None:
        """
        Initialize the adapter with configuration.

        This is called once after instantiation to set up the underlying
        simulator, load models, and prepare for simulation.

        Args:
            config: Configuration dictionary with model path, parameters, etc.
        """
        ...

    def advance_to(self, t: float) -> None:
        """
        Advance the simulation to time t.

        The adapter should internally handle any substeps needed to reach
        the target time. After this call, the adapter's state should reflect
        the simulation at time t.

        Args:
            t: Target simulation time to advance to.
        """
        ...

    def get_outputs(self) -> dict[str, BioSignal]:
        """
        Get current outputs as BioSignals.

        Returns signals for all exposed variables at the current simulation time.
        These signals can be consumed by other modules/adapters.

        Returns:
            Dictionary mapping signal names to BioSignal objects.
        """
        ...

    def set_inputs(self, signals: dict[str, BioSignal]) -> None:
        """
        Set inputs from external BioSignals.

        Receives signals from other modules/adapters and applies them
        to the underlying simulator (e.g., setting parameter values,
        injecting currents, etc.).

        Args:
            signals: Dictionary mapping signal names to BioSignal objects.
        """
        ...

    def get_state(self) -> dict[str, Any]:
        """
        Get serializable state for checkpointing.

        Returns a dictionary containing all state needed to restore
        the adapter to its current state later.

        Returns:
            Dictionary of serializable state.
        """
        ...

    def reset(self) -> None:
        """
        Reset the adapter to initial conditions.

        After reset, the adapter should be in the same state as after
        setup() was called.
        """
        ...


class BaseAdapter(ABC):
    """
    Abstract base class providing common adapter functionality.

    Adapters can inherit from this class to get default implementations
    of common methods while only implementing the core simulation logic.
    """

    def __init__(self, config: AdapterConfig | dict | None = None):
        """
        Initialize the adapter.

        Args:
            config: Adapter configuration. Can be AdapterConfig, dict, or None.
        """
        if config is None:
            self._config = AdapterConfig(adapter_type="base")
        elif isinstance(config, dict):
            self._config = AdapterConfig(**config)
        else:
            self._config = config

        self._current_time: float = 0.0
        self._is_setup: bool = False
        self._inputs: dict[str, BioSignal] = {}

    @property
    def config(self) -> AdapterConfig:
        """Get the adapter configuration."""
        return self._config

    @property
    def current_time(self) -> float:
        """Get the current simulation time."""
        return self._current_time

    @property
    def is_setup(self) -> bool:
        """Check if setup() has been called."""
        return self._is_setup

    def setup(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the adapter.

        Override _do_setup() in subclasses to implement initialization logic.

        Args:
            config: Optional additional configuration to merge.
        """
        if config:
            # Merge config into existing
            self._config.parameters.update(config.get("parameters", {}))
            self._config.extra.update(config.get("extra", {}))

        self._do_setup()
        self._is_setup = True

    @abstractmethod
    def _do_setup(self) -> None:
        """Implement setup logic in subclasses."""
        ...

    def set_inputs(self, signals: dict[str, BioSignal]) -> None:
        """Store inputs for use in advance_to()."""
        self._inputs.update(signals)

    def get_state(self) -> dict[str, Any]:
        """Get state for checkpointing. Override for custom state."""
        return {
            "current_time": self._current_time,
            "config": {
                "adapter_type": self._config.adapter_type,
                "parameters": self._config.parameters,
            },
        }

    def reset(self) -> None:
        """Reset to initial state. Override for custom reset logic."""
        self._current_time = 0.0
        self._inputs.clear()
        if self._is_setup:
            self._do_setup()

    @abstractmethod
    def advance_to(self, t: float) -> None:
        """Advance simulation to time t. Must be implemented by subclasses."""
        ...

    @abstractmethod
    def get_outputs(self) -> dict[str, BioSignal]:
        """Get current outputs. Must be implemented by subclasses."""
        ...

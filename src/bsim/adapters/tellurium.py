"""
TelluriumAdapter - Adapter for running SBML models via tellurium.

Tellurium is a Python-based environment for systems biology simulation.
This adapter wraps tellurium's roadrunner interface to run SBML models
within bsim's composition framework.

Requirements:
    pip install tellurium

Example:
    adapter = TelluriumAdapter(
        model_path="glycolysis.xml",
        expose=["glucose", "ATP", "pyruvate"],
        parameters={"k1": 0.5}
    )
    adapter.setup({})
    adapter.advance_to(10.0)
    outputs = adapter.get_outputs()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bsim.adapters.base import BaseAdapter, AdapterConfig
from bsim.adapters.signals import BioSignal, SignalMetadata


class TelluriumAdapter(BaseAdapter):
    """
    Adapter for running SBML models using tellurium/libroadrunner.

    This adapter wraps tellurium's roadrunner interface to:
    - Load SBML models from files or strings
    - Simulate with configurable parameters
    - Expose species concentrations and fluxes as BioSignals
    - Support parameter injection from other modules

    Attributes:
        model_path: Path to the SBML file or SBML string.
        expose: List of species/variables to expose as outputs.
        parameters: Parameter overrides to apply to the model.

    Example:
        >>> adapter = TelluriumAdapter(
        ...     model_path="model.xml",
        ...     expose=["S1", "S2"],
        ...     parameters={"k1": 0.1}
        ... )
        >>> adapter.setup({})
        >>> adapter.advance_to(10.0)
        >>> outputs = adapter.get_outputs()
        >>> print(outputs["S1"].value)
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        expose: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        sbml_string: str | None = None,
        config: AdapterConfig | dict | None = None,
    ):
        """
        Initialize the TelluriumAdapter.

        Args:
            model_path: Path to SBML file.
            expose: List of species/variables to expose as BioSignals.
            parameters: Parameter overrides for the model.
            sbml_string: SBML content as string (alternative to model_path).
            config: Full adapter configuration (overrides other args).
        """
        # Build config from arguments if not provided
        if config is None:
            config = AdapterConfig(
                adapter_type="tellurium",
                model_path=str(model_path) if model_path else None,
                expose=expose or [],
                parameters=parameters or {},
            )
        elif isinstance(config, dict):
            config = AdapterConfig(**config)

        super().__init__(config)

        self._sbml_string = sbml_string
        self._model = None
        self._species_ids: list[str] = []
        self._parameter_ids: list[str] = []

    def _do_setup(self) -> None:
        """Initialize the tellurium model."""
        try:
            import tellurium as te
        except ImportError as e:
            raise ImportError(
                "tellurium is required for TelluriumAdapter. "
                "Install with: pip install tellurium"
            ) from e

        # Load model from file or string
        if self._sbml_string:
            self._model = te.loada(self._sbml_string)
        elif self._config.model_path:
            path = Path(self._config.model_path)
            if not path.exists():
                raise FileNotFoundError(f"SBML file not found: {path}")
            self._model = te.loadSBMLModel(str(path))
        else:
            raise ValueError("Either model_path or sbml_string must be provided")

        # Get available species and parameters
        self._species_ids = list(self._model.getFloatingSpeciesIds())
        self._parameter_ids = list(self._model.getGlobalParameterIds())

        # Apply parameter overrides
        for name, value in self._config.parameters.items():
            if hasattr(self._model, name):
                setattr(self._model, name, value)
            else:
                # Try as a global parameter
                try:
                    self._model[name] = value
                except Exception:
                    pass  # Ignore unknown parameters

        # If no expose list, expose all floating species
        if not self._config.expose:
            self._config.expose = self._species_ids.copy()

        self._current_time = 0.0

    def advance_to(self, t: float) -> None:
        """
        Advance the simulation to time t.

        Args:
            t: Target simulation time.
        """
        if self._model is None:
            raise RuntimeError("Adapter not set up. Call setup() first.")

        if t <= self._current_time:
            return  # Already at or past this time

        # Apply any pending inputs
        for signal_name, signal in self._inputs.items():
            # Map signal name to model variable
            var_name = self._config.inputs.get(signal_name, signal_name)
            if hasattr(self._model, var_name):
                setattr(self._model, var_name, signal.value)
            else:
                try:
                    self._model[var_name] = signal.value
                except Exception:
                    pass  # Ignore unknown variables

        # Simulate from current time to target time
        # roadrunner uses relative times, so we need to be careful
        duration = t - self._current_time

        # Reset and simulate to get correct state
        # Note: tellurium's simulate() is cumulative, so we simulate the duration
        try:
            self._model.simulate(self._current_time, t, steps=max(2, int(duration * 10)))
        except Exception:
            # Fallback: just set values at steady state
            self._model.steadyState()

        self._current_time = t
        self._inputs.clear()

    def get_outputs(self) -> dict[str, BioSignal]:
        """
        Get current species concentrations as BioSignals.

        Returns:
            Dictionary mapping species names to BioSignal objects.
        """
        if self._model is None:
            return {}

        outputs = {}
        for name in self._config.expose:
            try:
                # Try to get the value from the model
                if hasattr(self._model, name):
                    value = getattr(self._model, name)
                else:
                    value = self._model[name]

                outputs[name] = BioSignal(
                    source="tellurium",
                    name=name,
                    value=float(value),
                    time=self._current_time,
                    metadata=SignalMetadata(
                        units="concentration",
                        description=f"Species {name} from SBML model",
                    ),
                )
            except Exception:
                # Skip variables that can't be read
                continue

        return outputs

    def get_state(self) -> dict[str, Any]:
        """Get state for checkpointing."""
        state = super().get_state()

        if self._model is not None:
            # Save current species concentrations
            state["species"] = {
                name: getattr(self._model, name, None)
                for name in self._species_ids
                if hasattr(self._model, name)
            }

        return state

    def reset(self) -> None:
        """Reset the model to initial conditions."""
        if self._model is not None:
            self._model.reset()
        self._current_time = 0.0
        self._inputs.clear()

    @property
    def species_ids(self) -> list[str]:
        """Get list of floating species IDs in the model."""
        return self._species_ids.copy()

    @property
    def parameter_ids(self) -> list[str]:
        """Get list of global parameter IDs in the model."""
        return self._parameter_ids.copy()

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        if self._model is None:
            return {}

        return {
            "species": self._species_ids,
            "parameters": self._parameter_ids,
            "reactions": list(self._model.getReactionIds()),
            "compartments": list(self._model.getCompartmentIds()),
        }

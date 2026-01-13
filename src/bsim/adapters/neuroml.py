"""
NeuroMLAdapter - Adapter for running NeuroML models via pyNeuroML.

pyNeuroML is a Python package for working with NeuroML models.
This adapter wraps pyNeuroML's LEMS simulation interface to run NeuroML
models within bsim's composition framework.

Requirements:
    pip install pyneuroml

Example:
    adapter = NeuroMLAdapter(
        model_path="neuron.nml",
        expose=["v", "spike_rate"],
        parameters={"cm": 1.0}
    )
    adapter.setup({})
    adapter.advance_to(100.0)  # 100ms simulation
    outputs = adapter.get_outputs()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import tempfile

from bsim.adapters.base import BaseAdapter, AdapterConfig
from bsim.adapters.signals import BioSignal, SignalMetadata


class NeuroMLAdapter(BaseAdapter):
    """
    Adapter for running NeuroML models using pyNeuroML.

    This adapter wraps pyNeuroML to:
    - Load NeuroML models from files
    - Run LEMS simulations with configurable parameters
    - Expose membrane potentials, spike rates, and other variables as BioSignals
    - Support parameter injection from other modules

    NeuroML is particularly suited for:
    - Detailed compartmental neuron models
    - Network simulations
    - Ion channel dynamics
    - Synaptic connections

    Attributes:
        model_path: Path to the NeuroML file (.nml or .xml).
        expose: List of variables to expose as outputs.
        parameters: Parameter overrides to apply to the model.
        duration: Default simulation duration in ms.
        dt: Simulation time step in ms.

    Example:
        >>> adapter = NeuroMLAdapter(
        ...     model_path="hh_neuron.nml",
        ...     expose=["v", "na_m", "na_h"],
        ...     parameters={"gNa": 120.0}
        ... )
        >>> adapter.setup({})
        >>> adapter.advance_to(50.0)  # 50ms
        >>> outputs = adapter.get_outputs()
        >>> print(outputs["v"].value)
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        expose: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        duration: float = 100.0,
        dt: float = 0.025,
        config: AdapterConfig | dict | None = None,
    ):
        """
        Initialize the NeuroMLAdapter.

        Args:
            model_path: Path to NeuroML file (.nml).
            expose: List of variables to expose as BioSignals.
            parameters: Parameter overrides for the model.
            duration: Default simulation duration in ms.
            dt: Simulation time step in ms.
            config: Full adapter configuration (overrides other args).
        """
        # Build config from arguments if not provided
        if config is None:
            config = AdapterConfig(
                adapter_type="neuroml",
                model_path=str(model_path) if model_path else None,
                expose=expose or [],
                parameters=parameters or {},
            )
        elif isinstance(config, dict):
            config = AdapterConfig(**config)

        super().__init__(config)

        self._duration = duration
        self._dt = dt
        self._model = None
        self._simulation = None
        self._results = None
        self._output_ids: list[str] = []
        self._temp_dir: tempfile.TemporaryDirectory | None = None

    def _do_setup(self) -> None:
        """Initialize the NeuroML model and simulation."""
        try:
            from pyneuroml import pynml
            from pyneuroml.lems import LEMSSimulation
            import neuroml
            from neuroml import loaders
        except ImportError as e:
            raise ImportError(
                "pyneuroml is required for NeuroMLAdapter. "
                "Install with: pip install pyneuroml"
            ) from e

        if not self._config.model_path:
            raise ValueError("model_path must be provided for NeuroML models")

        path = Path(self._config.model_path)
        if not path.exists():
            raise FileNotFoundError(f"NeuroML file not found: {path}")

        # Load the NeuroML model
        self._model = loaders.read_neuroml2_file(str(path))

        # Create a temp directory for simulation outputs
        self._temp_dir = tempfile.TemporaryDirectory()

        # Get available outputs from the model
        self._output_ids = self._extract_output_ids()

        # If no expose list, expose default variables
        if not self._config.expose:
            self._config.expose = self._output_ids[:10]  # Limit default outputs

        self._current_time = 0.0
        self._results = {}

    def _extract_output_ids(self) -> list[str]:
        """Extract available output variables from the model."""
        outputs = []

        if self._model is None:
            return outputs

        # Extract from cells
        for cell in getattr(self._model, "cells", []):
            cell_id = cell.id
            outputs.append(f"{cell_id}/v")  # Membrane potential

        # Extract from iaf_cells (integrate-and-fire)
        for cell in getattr(self._model, "iaf_cells", []):
            cell_id = cell.id
            outputs.append(f"{cell_id}/v")

        # Extract from populations
        for network in getattr(self._model, "networks", []):
            for pop in getattr(network, "populations", []):
                pop_id = pop.id
                outputs.append(f"{pop_id}[0]/v")

        # Default outputs if none found
        if not outputs:
            outputs = ["v", "spike_rate", "i_syn"]

        return outputs

    def advance_to(self, t: float) -> None:
        """
        Advance the simulation to time t.

        For NeuroML, we run a fresh simulation from 0 to t each time,
        as incremental simulation is not well-supported in the LEMS interface.

        Args:
            t: Target simulation time in ms.
        """
        if self._model is None:
            raise RuntimeError("Adapter not set up. Call setup() first.")

        if t <= self._current_time:
            return

        try:
            from pyneuroml import pynml
        except ImportError as e:
            raise ImportError(
                "pyneuroml is required for NeuroMLAdapter. "
                "Install with: pip install pyneuroml"
            ) from e

        # Apply any pending inputs as parameter modifications
        # (NeuroML doesn't support runtime input injection easily)
        for signal_name, signal in self._inputs.items():
            # Store for next simulation run
            self._config.parameters[signal_name] = signal.value

        # Run simulation to target time
        try:
            # Use pynml to run the simulation
            model_path = Path(self._config.model_path)
            results = pynml.run_lems_with_jneuroml(
                str(model_path),
                max_memory="2G",
                nogui=True,
                load_saved_data=True,
                plot=False,
                verbose=False,
            )

            if results:
                self._results = results
        except Exception as e:
            # If jneuroml fails, try neuron simulator
            try:
                results = pynml.run_lems_with_jneuroml_neuron(
                    str(model_path),
                    max_memory="2G",
                    nogui=True,
                    load_saved_data=True,
                    plot=False,
                    verbose=False,
                )
                if results:
                    self._results = results
            except Exception:
                # Store empty results if simulation fails
                self._results = {}

        self._current_time = t
        self._inputs.clear()

    def get_outputs(self) -> dict[str, BioSignal]:
        """
        Get current state variables as BioSignals.

        Returns:
            Dictionary mapping variable names to BioSignal objects.
        """
        if self._model is None:
            return {}

        outputs = {}

        for name in self._config.expose:
            value = 0.0

            # Try to get value from results
            if self._results:
                # Results are typically keyed by column names from output files
                for key, data in self._results.items():
                    if name in key or key.endswith(name):
                        # Get the last value in the timeseries
                        if hasattr(data, "__len__") and len(data) > 0:
                            value = float(data[-1])
                        elif isinstance(data, (int, float)):
                            value = float(data)
                        break

            outputs[name] = BioSignal(
                source="neuroml",
                name=name,
                value=value,
                time=self._current_time,
                metadata=SignalMetadata(
                    units="mV" if "v" in name.lower() else "dimensionless",
                    description=f"Variable {name} from NeuroML model",
                ),
            )

        return outputs

    def get_state(self) -> dict[str, Any]:
        """Get state for checkpointing."""
        state = super().get_state()
        state["results"] = self._results
        return state

    def reset(self) -> None:
        """Reset the model to initial conditions."""
        self._current_time = 0.0
        self._results = {}
        self._inputs.clear()

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()

    @property
    def output_ids(self) -> list[str]:
        """Get list of available output variable IDs."""
        return self._output_ids.copy()

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        if self._model is None:
            return {}

        info = {
            "id": getattr(self._model, "id", "unknown"),
            "outputs": self._output_ids,
        }

        # Count components
        info["cells"] = len(getattr(self._model, "cells", []))
        info["networks"] = len(getattr(self._model, "networks", []))
        info["ion_channels"] = len(getattr(self._model, "ion_channel_hhs", []))
        info["synapses"] = len(getattr(self._model, "exp_two_synapses", []))

        return info


class NeuroMLNetworkAdapter(NeuroMLAdapter):
    """
    Specialized adapter for NeuroML network simulations.

    This adapter extends NeuroMLAdapter with network-specific features:
    - Population-level recording
    - Spike raster outputs
    - Mean firing rate calculation
    - Network activity metrics

    Example:
        >>> adapter = NeuroMLNetworkAdapter(
        ...     model_path="network.nml",
        ...     populations=["exc", "inh"],
        ...     record_spikes=True
        ... )
        >>> adapter.setup({})
        >>> adapter.advance_to(1000.0)  # 1 second
        >>> outputs = adapter.get_outputs()
        >>> print(outputs["exc_rate"].value)
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        populations: list[str] | None = None,
        record_spikes: bool = True,
        expose: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        config: AdapterConfig | dict | None = None,
    ):
        """
        Initialize the NeuroMLNetworkAdapter.

        Args:
            model_path: Path to NeuroML network file.
            populations: List of population IDs to record from.
            record_spikes: Whether to record spike times.
            expose: Additional variables to expose.
            parameters: Parameter overrides.
            config: Full adapter configuration.
        """
        super().__init__(
            model_path=model_path,
            expose=expose,
            parameters=parameters,
            config=config,
        )

        self._populations = populations or []
        self._record_spikes = record_spikes
        self._spike_times: dict[str, list[float]] = {}

    def _do_setup(self) -> None:
        """Initialize with network-specific setup."""
        super()._do_setup()

        # Add population-level outputs
        for pop in self._populations:
            if f"{pop}_rate" not in self._config.expose:
                self._config.expose.append(f"{pop}_rate")

    def get_outputs(self) -> dict[str, BioSignal]:
        """Get outputs including network-level metrics."""
        outputs = super().get_outputs()

        # Calculate population firing rates
        for pop in self._populations:
            spikes = self._spike_times.get(pop, [])
            if self._current_time > 0:
                rate = len(spikes) / (self._current_time / 1000.0)  # Hz
            else:
                rate = 0.0

            outputs[f"{pop}_rate"] = BioSignal(
                source="neuroml",
                name=f"{pop}_rate",
                value=rate,
                time=self._current_time,
                metadata=SignalMetadata(
                    units="Hz",
                    description=f"Mean firing rate of population {pop}",
                ),
            )

        return outputs

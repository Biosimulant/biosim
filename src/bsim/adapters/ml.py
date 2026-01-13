"""
MLAdapter - Adapter for running ONNX ML models in simulation loops.

This adapter wraps ONNX runtime to run trained ML models as part of
bsim simulations. ML models receive inputs from other modules via BioSignals
and emit predictions that can be consumed by downstream modules.

Requirements:
    pip install onnxruntime

Example:
    adapter = MLAdapter(
        model_path="predictor.onnx",
        inputs={"glucose": "input_glucose", "lactate": "input_lactate"},
        outputs={"prediction": "drug_efficacy"}
    )
    adapter.setup({})
    adapter.set_inputs({"glucose": BioSignal(..., value=5.0)})
    adapter.advance_to(1.0)  # Run inference
    outputs = adapter.get_outputs()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from bsim.adapters.base import BaseAdapter, AdapterConfig
from bsim.adapters.signals import BioSignal, SignalMetadata


class MLAdapter(BaseAdapter):
    """
    Adapter for running ONNX ML models in simulation loops.

    This adapter enables hybrid simulations where ML models predict
    outcomes based on inputs from mechanistic models. The ML model
    runs inference at each simulation step, receiving inputs as
    BioSignals and emitting predictions.

    Unlike time-stepping simulators, ML models are stateless - they
    simply transform inputs to outputs. The advance_to() method
    triggers inference with the current inputs.

    Attributes:
        model_path: Path to the ONNX model file.
        inputs: Mapping from BioSignal names to model input names.
        outputs: Mapping from model output names to BioSignal names.

    Example:
        >>> adapter = MLAdapter(
        ...     model_path="drug_response.onnx",
        ...     inputs={"glucose": "x1", "lactate": "x2"},
        ...     outputs={"efficacy": "y"}
        ... )
        >>> adapter.setup({})
        >>> adapter.set_inputs({
        ...     "glucose": BioSignal("metabolism", "glucose", 5.0, 0.0),
        ...     "lactate": BioSignal("metabolism", "lactate", 2.0, 0.0),
        ... })
        >>> adapter.advance_to(1.0)
        >>> outputs = adapter.get_outputs()
        >>> print(outputs["efficacy"].value)
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        inputs: dict[str, str] | None = None,
        outputs: dict[str, str] | None = None,
        config: AdapterConfig | dict | None = None,
    ):
        """
        Initialize the MLAdapter.

        Args:
            model_path: Path to ONNX model file.
            inputs: Mapping of BioSignal names to model input names.
            outputs: Mapping of model output names to BioSignal names.
            config: Full adapter configuration (overrides other args).
        """
        if config is None:
            config = AdapterConfig(
                adapter_type="ml",
                model_path=str(model_path) if model_path else None,
                inputs=inputs or {},
                outputs=outputs or {},
            )
        elif isinstance(config, dict):
            config = AdapterConfig(**config)

        super().__init__(config)

        self._session = None
        self._input_names: list[str] = []
        self._output_names: list[str] = []
        self._input_shapes: dict[str, tuple] = {}
        self._current_outputs: dict[str, Any] = {}

    def _do_setup(self) -> None:
        """Initialize the ONNX runtime session."""
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ImportError(
                "onnxruntime is required for MLAdapter. "
                "Install with: pip install onnxruntime"
            ) from e

        if not self._config.model_path:
            raise ValueError("model_path must be provided for MLAdapter")

        path = Path(self._config.model_path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")

        # Create inference session
        self._session = ort.InferenceSession(str(path))

        # Get input/output metadata
        self._input_names = [inp.name for inp in self._session.get_inputs()]
        self._output_names = [out.name for out in self._session.get_outputs()]

        # Get input shapes for validation
        for inp in self._session.get_inputs():
            shape = inp.shape
            # Replace dynamic dimensions with None
            shape = tuple(None if isinstance(d, str) else d for d in shape)
            self._input_shapes[inp.name] = shape

        # Set up input/output mappings if not provided
        if not self._config.inputs:
            # Default: use model input names directly
            self._config.inputs = {name: name for name in self._input_names}

        if not self._config.outputs:
            # Default: use model output names directly
            self._config.outputs = {name: name for name in self._output_names}

        self._current_outputs.clear()

    def advance_to(self, t: float) -> None:
        """
        Run inference with current inputs.

        For ML models, this runs a forward pass using the accumulated
        inputs. The model is stateless - time only affects the timestamp
        on output signals.

        Args:
            t: Target simulation time (used for output timestamps).
        """
        if self._session is None:
            raise RuntimeError("Adapter not set up. Call setup() first.")

        # Build input dictionary for ONNX
        onnx_inputs = {}

        for signal_name, model_input_name in self._config.inputs.items():
            if signal_name in self._inputs:
                signal = self._inputs[signal_name]
                value = signal.value

                # Convert to numpy array with correct shape
                if isinstance(value, (int, float)):
                    value = np.array([[value]], dtype=np.float32)
                elif isinstance(value, (list, tuple)):
                    value = np.array(value, dtype=np.float32)
                elif isinstance(value, np.ndarray):
                    value = value.astype(np.float32)

                # Ensure batch dimension
                if value.ndim == 1:
                    value = value.reshape(1, -1)

                onnx_inputs[model_input_name] = value
            else:
                # Use zeros for missing inputs
                shape = self._input_shapes.get(model_input_name, (1, 1))
                # Replace None with 1 for dynamic dimensions
                shape = tuple(1 if d is None else d for d in shape)
                onnx_inputs[model_input_name] = np.zeros(shape, dtype=np.float32)

        # Run inference
        try:
            results = self._session.run(None, onnx_inputs)

            # Store outputs
            for i, output_name in enumerate(self._output_names):
                if output_name in self._config.outputs:
                    signal_name = self._config.outputs[output_name]
                    value = results[i]

                    # Unwrap single values
                    if isinstance(value, np.ndarray):
                        if value.size == 1:
                            value = float(value.flat[0])
                        else:
                            value = value.squeeze()

                    self._current_outputs[signal_name] = value

        except Exception as e:
            # Log error but don't crash
            print(f"MLAdapter inference error: {e}")

        self._current_time = t
        self._inputs.clear()

    def get_outputs(self) -> dict[str, BioSignal]:
        """
        Get model predictions as BioSignals.

        Returns:
            Dictionary mapping signal names to BioSignal objects.
        """
        outputs = {}

        for signal_name, value in self._current_outputs.items():
            outputs[signal_name] = BioSignal(
                source="ml",
                name=signal_name,
                value=value,
                time=self._current_time,
                metadata=SignalMetadata(
                    description=f"ML model prediction: {signal_name}",
                ),
            )

        return outputs

    def get_state(self) -> dict[str, Any]:
        """Get state for checkpointing."""
        state = super().get_state()
        state["current_outputs"] = {
            k: v.tolist() if isinstance(v, np.ndarray) else v
            for k, v in self._current_outputs.items()
        }
        return state

    def reset(self) -> None:
        """Reset the adapter state."""
        self._current_time = 0.0
        self._inputs.clear()
        self._current_outputs.clear()

    @property
    def input_names(self) -> list[str]:
        """Get the ONNX model's input names."""
        return self._input_names.copy()

    @property
    def output_names(self) -> list[str]:
        """Get the ONNX model's output names."""
        return self._output_names.copy()

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded ONNX model."""
        if self._session is None:
            return {}

        return {
            "inputs": [
                {
                    "name": inp.name,
                    "shape": inp.shape,
                    "type": inp.type,
                }
                for inp in self._session.get_inputs()
            ],
            "outputs": [
                {
                    "name": out.name,
                    "shape": out.shape,
                    "type": out.type,
                }
                for out in self._session.get_outputs()
            ],
        }

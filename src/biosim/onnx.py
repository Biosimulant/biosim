# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Optional ONNX-backed biomodules."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

from .modules import BioModule
from .signals import BioSignal, SignalMetadata


def _flatten_numeric_items(value: Any) -> List[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        return [float(item) for item in value if isinstance(item, (int, float))]
    if isinstance(value, (int, float)):
        return [float(value)]
    return []


class OnnxClassifierModule(BioModule):
    """Run an ONNX classifier behind the standard BioModule contract."""

    def __init__(
        self,
        model_path: str,
        *,
        class_labels: Optional[Sequence[str]] = None,
        input_port: str = "state_vector",
        probabilities_port: str = "state_probabilities",
        predicted_port: str = "predicted_state",
        model_input_name: Optional[str] = None,
        model_output_name: Optional[str] = None,
        base_dir: Optional[str] = None,
        input_vector_length: Optional[int] = None,
        min_dt: float = 0.001,
        session_factory: Optional[Callable[[str], Any]] = None,
        providers: Optional[Sequence[str]] = None,
        probabilities_description: str = "Classifier probabilities over the declared ONNX class labels",
        predicted_description: str = "Most likely ONNX-predicted state",
    ) -> None:
        self.min_dt = min_dt
        self.model_path = model_path
        self.class_labels = list(class_labels or ["class_0"])
        self.input_port = input_port
        self.probabilities_port = probabilities_port
        self.predicted_port = predicted_port
        self._input_name = model_input_name or input_port
        self._output_name = model_output_name or probabilities_port
        self.base_dir = Path(base_dir).resolve() if base_dir else None
        self.input_vector_length = input_vector_length
        self._session_factory = session_factory
        self.providers = list(providers or ["CPUExecutionProvider"])
        self.probabilities_description = probabilities_description
        self.predicted_description = predicted_description
        self._session: Any = None
        self._latest_vector: List[float] = []
        self._latest_probs: List[float] = [1.0] + [0.0] * (len(self.class_labels) - 1)
        self._latest_label: str = self.class_labels[0]
        self._outputs: Dict[str, BioSignal] = {}

    def inputs(self) -> Set[str]:
        return {self.input_port}

    def outputs(self) -> Set[str]:
        return {self.probabilities_port, self.predicted_port}

    def reset(self) -> None:
        self._latest_vector = []
        self._latest_probs = [1.0] + [0.0] * (len(self.class_labels) - 1)
        self._latest_label = self.class_labels[0]
        self._outputs = {}

    def _resolved_model_path(self) -> str:
        path = Path(self.model_path)
        if path.is_absolute():
            return str(path)
        if self.base_dir is not None:
            return str((self.base_dir / path).resolve())
        return str(path.resolve())

    def _default_session_factory(self) -> Callable[[str], Any]:
        ort = importlib.import_module("onnxruntime")
        return lambda model_path: ort.InferenceSession(model_path, providers=self.providers)

    def _ensure_session(self) -> Any:
        if self._session is None:
            factory = self._session_factory or self._default_session_factory()
            self._session = factory(self._resolved_model_path())
            inputs = getattr(self._session, "get_inputs", lambda: [])()
            outputs = getattr(self._session, "get_outputs", lambda: [])()
            if inputs:
                self._input_name = str(inputs[0].name)
            if outputs:
                self._output_name = str(outputs[0].name)
        return self._session

    def _normalize_input_value(self, raw: Any) -> List[float]:
        if isinstance(raw, dict):
            raw = raw.get("features", raw)
        vector = _flatten_numeric_items(raw)
        if self.input_vector_length is not None:
            vector = vector[: self.input_vector_length]
            while len(vector) < self.input_vector_length:
                vector.append(0.0)
        return vector

    def set_inputs(self, signals: Dict[str, BioSignal]) -> None:
        signal = signals.get(self.input_port)
        if signal is None:
            return
        self._latest_vector = self._normalize_input_value(signal.value)

    def _run_inference(self) -> List[float]:
        session = self._ensure_session()
        vector: List[Iterable[float]] = [self._latest_vector]
        result = session.run([self._output_name], {self._input_name: vector})
        if not result:
            return [1.0] + [0.0] * (len(self.class_labels) - 1)
        probs = _flatten_numeric_items(result[0])
        return probs or ([1.0] + [0.0] * (len(self.class_labels) - 1))

    def advance_to(self, t: float) -> None:
        probs = self._run_inference()
        if len(probs) < len(self.class_labels):
            probs = probs + [0.0] * (len(self.class_labels) - len(probs))
        self._latest_probs = probs[: len(self.class_labels)]
        max_idx = max(range(len(self._latest_probs)), key=self._latest_probs.__getitem__)
        self._latest_label = self.class_labels[max_idx]

        source = getattr(self, "_world_name", self.__class__.__name__)
        self._outputs = {
            self.probabilities_port: BioSignal(
                source=source,
                name=self.probabilities_port,
                value=list(self._latest_probs),
                time=t,
                metadata=SignalMetadata(
                    description=self.probabilities_description,
                    dtype="float32",
                    shape=(len(self.class_labels),),
                    kind="state",
                ),
            ),
            self.predicted_port: BioSignal(
                source=source,
                name=self.predicted_port,
                value={
                    "label": self._latest_label,
                    "probabilities": dict(zip(self.class_labels, self._latest_probs)),
                },
                time=t,
                metadata=SignalMetadata(description=self.predicted_description, kind="state"),
            ),
        }

    def get_outputs(self) -> Dict[str, BioSignal]:
        return dict(self._outputs)

    def get_state(self) -> Dict[str, Any]:
        return {
            "input_port": self.input_port,
            "model_path": self.model_path,
            "latest_vector": list(self._latest_vector),
            "latest_probs": list(self._latest_probs),
            "latest_label": self._latest_label,
        }

    def visualize(self) -> Optional[Dict[str, Any]]:
        if not self._outputs:
            return None
        return {
            "render": "bar",
            "data": {
                "items": [
                    {"label": label, "value": prob}
                    for label, prob in zip(self.class_labels, self._latest_probs)
                ]
            },
            "description": f"Latest ONNX classification result: {self._latest_label}.",
        }

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest


class _FakeSession:
    def __init__(self) -> None:
        self.seen = []

    def get_inputs(self):
        return [SimpleNamespace(name="state_vector")]

    def get_outputs(self):
        return [SimpleNamespace(name="state_probabilities")]

    def run(self, output_names, feed_dict):
        self.seen.append((tuple(output_names), dict(feed_dict)))
        return [np.asarray([[0.1, 0.2, 0.7]], dtype=np.float32)]


def test_onnx_classifier_emits_probabilities_and_label(biosim):
    session = _FakeSession()
    module = biosim.OnnxClassifierModule(
        model_path="artifacts/demo.onnx",
        class_labels=["quiescent", "subthreshold", "spiking"],
        session_factory=lambda model_path: session,
        input_vector_length=4,
    )

    module.set_inputs(
        {
            "state_vector": biosim.BioSignal(
                source="adapter",
                name="state_vector",
                value=[-64.0, 0.1, 0.6, 0.3],
                time=0.0,
            )
        }
    )
    module.advance_to(0.001)

    outputs = module.get_outputs()
    assert outputs["state_probabilities"].value == pytest.approx([0.1, 0.2, 0.7])
    assert outputs["state_probabilities"].metadata.shape == (3,)
    assert outputs["predicted_state"].value["label"] == "spiking"
    assert session.seen[0][0] == ("state_probabilities",)
    assert session.seen[0][1]["state_vector"] == [[-64.0, 0.1, 0.6, 0.3]]


def test_onnx_classifier_normalizes_feature_dict_input(biosim):
    session = _FakeSession()
    module = biosim.OnnxClassifierModule(
        model_path="artifacts/demo.onnx",
        class_labels=["baseline", "active", "burst"],
        input_port="features",
        probabilities_port="scores",
        predicted_port="label",
        session_factory=lambda model_path: session,
        input_vector_length=4,
    )

    module.set_inputs(
        {
            "features": biosim.BioSignal(
                source="adapter",
                name="features",
                value={"features": [1, 2]},
                time=0.0,
            )
        }
    )
    module.advance_to(0.1)

    outputs = module.get_outputs()
    assert outputs["scores"].value == pytest.approx([0.1, 0.2, 0.7])
    assert outputs["label"].value["label"] == "burst"
    assert session.seen[0][1]["state_vector"] == [[1.0, 2.0, 0.0, 0.0]]

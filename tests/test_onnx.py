from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from biosim.onnx import _flatten_numeric_items


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
            "state_vector": biosim.ArraySignal(
                source="adapter",
                name="state_vector",
                value=[-64.0, 0.1, 0.6, 0.3],
                emitted_at=0.0,
                spec=biosim.SignalSpec.array(dtype="float32", shape=(4,)),
            )
        }
    )
    module.advance_window(0.0, 0.001)

    outputs = module.get_outputs()
    assert outputs["state_probabilities"].value == pytest.approx([0.1, 0.2, 0.7])
    assert outputs["state_probabilities"].spec is not None
    assert outputs["state_probabilities"].spec.shape == (3,)
    assert outputs["predicted_state"].value["label"] == "spiking"
    assert session.seen[0][0] == ("state_probabilities",)
    assert session.seen[0][1]["state_vector"][0] == pytest.approx([-64.0, 0.1, 0.6, 0.3])


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
            "features": biosim.RecordSignal(
                source="adapter",
                name="features",
                value={"features": [1, 2]},
                emitted_at=0.0,
                spec=biosim.SignalSpec.record(schema={"features": "list"}),
            )
        }
    )
    module.advance_window(0.0, 0.1)

    outputs = module.get_outputs()
    assert outputs["scores"].value == pytest.approx([0.1, 0.2, 0.7])
    assert outputs["label"].value["label"] == "burst"
    assert session.seen[0][1]["state_vector"][0] == pytest.approx([1.0, 2.0, 0.0, 0.0])


def test_onnx_classifier_uses_zero_vector_before_first_input(biosim):
    session = _FakeSession()
    module = biosim.OnnxClassifierModule(
        model_path="artifacts/demo.onnx",
        class_labels=["quiescent", "subthreshold", "spiking"],
        session_factory=lambda model_path: session,
        input_vector_length=4,
    )

    module.advance_window(0.0, 0.001)

    outputs = module.get_outputs()
    assert outputs["state_probabilities"].value == pytest.approx([0.1, 0.2, 0.7])
    assert outputs["predicted_state"].value["label"] == "spiking"
    assert session.seen[0][1]["state_vector"][0] == pytest.approx([0.0, 0.0, 0.0, 0.0])


def test_flatten_numeric_items_handles_common_model_output_shapes() -> None:
    assert _flatten_numeric_items(np.asarray([[1, 2, 3]], dtype=np.float32)) == [1.0, 2.0, 3.0]
    assert _flatten_numeric_items((1, 2, "bad")) == [1.0, 2.0]
    assert _flatten_numeric_items(4) == [4.0]
    assert _flatten_numeric_items({"not": "numeric"}) == []


def test_onnx_classifier_handles_missing_input_and_empty_session_result(biosim, tmp_path):
    class EmptySession:
        def get_inputs(self):
            return []

        def get_outputs(self):
            return []

        def run(self, output_names, feed_dict):
            assert output_names == ["scores"]
            assert feed_dict == {"features": [[0.0, 0.0]]}
            return []

    seen_paths = []

    def factory(model_path: str):
        seen_paths.append(model_path)
        return EmptySession()

    module = biosim.OnnxClassifierModule(
        model_path="model.onnx",
        base_dir=str(tmp_path),
        class_labels=["baseline", "active"],
        input_port="features",
        probabilities_port="scores",
        predicted_port="label",
        model_input_name="features",
        model_output_name="scores",
        session_factory=factory,
        input_vector_length=2,
    )

    assert module.visualize() is None
    module.set_inputs({})
    module.advance_window(0.0, 0.1)

    assert seen_paths == [str(tmp_path / "model.onnx")]
    outputs = module.get_outputs()
    assert outputs["scores"].value == pytest.approx([1.0, 0.0])
    assert outputs["label"].value["label"] == "baseline"
    assert module.visualize()["data"]["items"][0] == {"label": "baseline", "value": 1.0}


def test_onnx_classifier_pads_short_probabilities_and_round_trips_state(biosim):
    class ShortSession:
        def run(self, output_names, feed_dict):
            return [[0.25]]

    module = biosim.OnnxClassifierModule(
        model_path="/tmp/model.onnx",
        class_labels=["one", "two", "three"],
        session_factory=lambda _path: ShortSession(),
        input_vector_length=3,
    )
    module.set_inputs(
        {
            "state_vector": biosim.RecordSignal(
                source="adapter",
                name="state_vector",
                value={"features": [9, 8, 7, 6]},
                emitted_at=0.0,
                spec=biosim.SignalSpec.record(schema={"features": "list"}),
            )
        }
    )
    module.advance_window(0.0, 0.2)

    assert module.get_outputs()["state_probabilities"].value == pytest.approx([0.25, 0.0, 0.0])
    snapshot = module.snapshot()

    restored = biosim.OnnxClassifierModule(
        model_path="/tmp/model.onnx",
        class_labels=["one", "two", "three"],
        session_factory=lambda _path: ShortSession(),
        input_vector_length=3,
    )
    restored.restore(snapshot)
    state = restored.__getstate__()

    assert restored.snapshot()["latest_vector"] == [9.0, 8.0, 7.0]
    assert restored.snapshot()["latest_label"] == "one"
    assert state["_session"] is None
    restored.reset()
    assert restored.get_outputs() == {}

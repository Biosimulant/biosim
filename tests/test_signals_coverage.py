"""Tests for biosim.signals – cover all uncovered lines."""
import numpy as np
import pytest

from biosim.signals import BioSignal, SignalMetadata


def test_signal_metadata_shape_list_to_tuple():
    """SignalMetadata should convert list shapes to tuples."""
    meta = SignalMetadata(shape=[3, 4])
    assert meta.shape == (3, 4)
    assert isinstance(meta.shape, tuple)


def test_signal_metadata_all_fields():
    meta = SignalMetadata(
        units="mV",
        shape=(10,),
        description="test signal",
        min_value=-100.0,
        max_value=100.0,
        dtype="float64",
        kind="event",
    )
    assert meta.units == "mV"
    assert meta.shape == (10,)
    assert meta.kind == "event"


def test_biosignal_metadata_from_dict():
    """BioSignal.__post_init__ should convert dict metadata to SignalMetadata."""
    sig = BioSignal(
        source="mod",
        name="x",
        value=1.0,
        time=0.0,
        metadata={"units": "Hz", "kind": "state"},
    )
    assert isinstance(sig.metadata, SignalMetadata)
    assert sig.metadata.units == "Hz"


def test_biosignal_is_scalar():
    sig = BioSignal(source="m", name="x", value=42.0, time=0.0)
    assert sig.is_scalar is True
    assert sig.is_array is False


def test_biosignal_is_array_list():
    sig = BioSignal(source="m", name="x", value=[1, 2, 3], time=0.0)
    assert sig.is_scalar is False
    assert sig.is_array is True


def test_biosignal_is_array_numpy():
    sig = BioSignal(source="m", name="x", value=np.array([1, 2]), time=0.0)
    assert sig.is_array is True


def test_biosignal_is_array_tuple():
    sig = BioSignal(source="m", name="x", value=(1, 2), time=0.0)
    assert sig.is_array is True


def test_biosignal_as_float():
    sig = BioSignal(source="m", name="x", value=3.14, time=0.0)
    assert sig.as_float() == pytest.approx(3.14)


def test_biosignal_as_float_raises_for_array():
    sig = BioSignal(source="m", name="x", value=[1, 2], time=0.0)
    with pytest.raises(ValueError, match="array"):
        sig.as_float()


def test_biosignal_as_array_from_list():
    sig = BioSignal(source="m", name="x", value=[1, 2, 3], time=0.0)
    arr = sig.as_array()
    assert isinstance(arr, np.ndarray)
    np.testing.assert_array_equal(arr, [1, 2, 3])


def test_biosignal_as_array_passthrough():
    original = np.array([4, 5, 6])
    sig = BioSignal(source="m", name="x", value=original, time=0.0)
    arr = sig.as_array()
    assert arr is original


def test_biosignal_to_dict_scalar():
    sig = BioSignal(source="m", name="x", value=1.0, time=0.5)
    d = sig.to_dict()
    assert d["source"] == "m"
    assert d["name"] == "x"
    assert d["value"] == 1.0
    assert d["time"] == 0.5
    assert d["metadata"]["kind"] == "state"


def test_biosignal_to_dict_ndarray():
    sig = BioSignal(source="m", name="x", value=np.array([1, 2]), time=0.0)
    d = sig.to_dict()
    assert d["value"] == [1, 2]


def test_biosignal_from_dict():
    data = {
        "source": "s",
        "name": "n",
        "value": 99,
        "time": 1.0,
        "metadata": {"units": "mM", "kind": "event"},
    }
    sig = BioSignal.from_dict(data)
    assert sig.source == "s"
    assert sig.name == "n"
    assert sig.value == 99
    assert sig.time == 1.0
    assert sig.metadata.units == "mM"
    assert sig.metadata.kind == "event"


def test_biosignal_from_dict_no_metadata():
    data = {"source": "s", "name": "n", "value": 0, "time": 0.0}
    sig = BioSignal.from_dict(data)
    assert isinstance(sig.metadata, SignalMetadata)

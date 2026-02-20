def test_exports(biosim):
    assert hasattr(biosim, "__version__")
    assert hasattr(biosim, "BioWorld")
    assert hasattr(biosim, "WorldEvent")
    assert hasattr(biosim, "BioSignal")

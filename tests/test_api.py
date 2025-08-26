def test_exports(bsim):
    assert hasattr(bsim, "__version__")
    assert hasattr(bsim, "BioWorld")
    assert hasattr(bsim, "BioWorldEvent")
    assert hasattr(bsim, "Solver")
    assert hasattr(bsim, "FixedStepSolver")

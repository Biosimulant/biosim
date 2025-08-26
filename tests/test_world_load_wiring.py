from pathlib import Path


def test_world_load_wiring_example_file(bsim):
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    world.load_wiring(str(Path("examples/configs/brain.toml")))
    # Should load and simulate without exceptions
    world.simulate(steps=1, dt=0.1)

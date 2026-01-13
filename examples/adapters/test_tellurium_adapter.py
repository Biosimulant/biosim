#!/usr/bin/env python3
"""
Test script for TelluriumAdapter with a real SBML model.

This script downloads a model from BioModels and runs it through
the adapter to verify everything works end-to-end.

Usage:
    pip install bsim[tellurium]
    python test_tellurium_adapter.py
"""

import tempfile
from pathlib import Path

# Simple SBML model for testing (Michaelis-Menten kinetics)
SIMPLE_SBML = """<?xml version="1.0" encoding="UTF-8"?>
<sbml xmlns="http://www.sbml.org/sbml/level3/version2/core" level="3" version="2">
  <model id="simple_enzyme" name="Simple Enzyme Kinetics">
    <listOfCompartments>
      <compartment id="cell" size="1" constant="true"/>
    </listOfCompartments>
    <listOfSpecies>
      <species id="S" compartment="cell" initialConcentration="10" hasOnlySubstanceUnits="false" boundaryCondition="false" constant="false"/>
      <species id="E" compartment="cell" initialConcentration="1" hasOnlySubstanceUnits="false" boundaryCondition="false" constant="false"/>
      <species id="ES" compartment="cell" initialConcentration="0" hasOnlySubstanceUnits="false" boundaryCondition="false" constant="false"/>
      <species id="P" compartment="cell" initialConcentration="0" hasOnlySubstanceUnits="false" boundaryCondition="false" constant="false"/>
    </listOfSpecies>
    <listOfParameters>
      <parameter id="k1" value="0.1" constant="true"/>
      <parameter id="k2" value="0.05" constant="true"/>
      <parameter id="k3" value="0.1" constant="true"/>
    </listOfParameters>
    <listOfReactions>
      <reaction id="binding" reversible="false">
        <listOfReactants>
          <speciesReference species="S" stoichiometry="1" constant="true"/>
          <speciesReference species="E" stoichiometry="1" constant="true"/>
        </listOfReactants>
        <listOfProducts>
          <speciesReference species="ES" stoichiometry="1" constant="true"/>
        </listOfProducts>
        <kineticLaw>
          <math xmlns="http://www.w3.org/1998/Math/MathML">
            <apply>
              <times/>
              <ci>k1</ci>
              <ci>S</ci>
              <ci>E</ci>
            </apply>
          </math>
        </kineticLaw>
      </reaction>
      <reaction id="unbinding" reversible="false">
        <listOfReactants>
          <speciesReference species="ES" stoichiometry="1" constant="true"/>
        </listOfReactants>
        <listOfProducts>
          <speciesReference species="S" stoichiometry="1" constant="true"/>
          <speciesReference species="E" stoichiometry="1" constant="true"/>
        </listOfProducts>
        <kineticLaw>
          <math xmlns="http://www.w3.org/1998/Math/MathML">
            <apply>
              <times/>
              <ci>k2</ci>
              <ci>ES</ci>
            </apply>
          </math>
        </kineticLaw>
      </reaction>
      <reaction id="catalysis" reversible="false">
        <listOfReactants>
          <speciesReference species="ES" stoichiometry="1" constant="true"/>
        </listOfReactants>
        <listOfProducts>
          <speciesReference species="E" stoichiometry="1" constant="true"/>
          <speciesReference species="P" stoichiometry="1" constant="true"/>
        </listOfProducts>
        <kineticLaw>
          <math xmlns="http://www.w3.org/1998/Math/MathML">
            <apply>
              <times/>
              <ci>k3</ci>
              <ci>ES</ci>
            </apply>
          </math>
        </kineticLaw>
      </reaction>
    </listOfReactions>
  </model>
</sbml>
"""


def test_tellurium_adapter():
    """Test the TelluriumAdapter with a simple SBML model."""
    print("=" * 60)
    print("Testing TelluriumAdapter")
    print("=" * 60)

    # Check tellurium is installed
    try:
        import tellurium as te
        print(f"✓ Tellurium version: {te.__version__}")
    except ImportError:
        print("✗ Tellurium not installed. Run: pip install bsim[tellurium]")
        return False

    # Import adapter
    try:
        from bsim.adapters import TelluriumAdapter
        from bsim.adapters.base import AdapterConfig
        print("✓ TelluriumAdapter imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import adapter: {e}")
        return False

    # Create temp file with SBML
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(SIMPLE_SBML)
        sbml_path = f.name

    print(f"✓ Created test SBML file: {sbml_path}")

    # Create adapter config
    config = AdapterConfig(
        adapter_type="tellurium",
        model_path=sbml_path,
        expose=["S", "E", "ES", "P"],
        parameters={"k1": 0.2},  # Override k1
    )

    # Create and setup adapter
    adapter = TelluriumAdapter(config)
    adapter.setup({})
    print("✓ Adapter setup complete")

    # Check initial outputs
    outputs = adapter.get_outputs()
    print(f"✓ Initial outputs: {list(outputs.keys())}")
    for name, signal in outputs.items():
        print(f"  {name} = {signal.value:.4f}")

    # Run simulation
    print("\nRunning simulation...")
    times = [0, 10, 20, 30, 40, 50]
    for t in times[1:]:
        adapter.advance_to(t)
        outputs = adapter.get_outputs()
        s_val = outputs["S"].value
        p_val = outputs["P"].value
        print(f"  t={t:3d}: S={s_val:.4f}, P={p_val:.4f}")

    # Verify product formed
    final_p = outputs["P"].value
    if final_p > 1.0:
        print(f"\n✓ Product formed: P = {final_p:.4f}")
    else:
        print(f"\n✗ No product formed: P = {final_p:.4f}")
        return False

    # Test reset
    adapter.reset()
    outputs = adapter.get_outputs()
    reset_s = outputs["S"].value
    if abs(reset_s - 10.0) < 0.1:
        print(f"✓ Reset works: S = {reset_s:.4f} (expected ~10)")
    else:
        print(f"✗ Reset failed: S = {reset_s:.4f} (expected ~10)")
        return False

    # Cleanup
    Path(sbml_path).unlink()
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
    return True


def test_adapter_in_wiring():
    """Test using the adapter through the wiring system."""
    print("\n" + "=" * 60)
    print("Testing Adapter in Wiring System")
    print("=" * 60)

    try:
        import tellurium
    except ImportError:
        print("✗ Tellurium not installed, skipping wiring test")
        return True

    import tempfile
    from bsim import BioWorld
    from bsim.wiring import build_from_spec

    # Create temp SBML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(SIMPLE_SBML)
        sbml_path = f.name

    # Create world
    world = BioWorld(dt=1.0)

    # Build from spec with adapter
    spec = {
        "modules": {
            "enzyme_model": {
                "adapter": "tellurium",
                "model": sbml_path,
                "expose": ["S", "P"],
                "parameters": {"k1": 0.15},
            }
        }
    }

    try:
        builder = build_from_spec(world, spec)
        print("✓ Adapter module created through wiring")

        # Get the module
        module = builder.registry["enzyme_model"]
        print(f"✓ Module type: {type(module).__name__}")

        # Check declared ports
        print(f"✓ Declared outputs: {module.outputs()}")

        # Step the world
        for _ in range(10):
            world.step()

        print("✓ World stepped successfully")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        Path(sbml_path).unlink()

    print("=" * 60)
    print("Wiring test passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_tellurium_adapter()
    if success:
        test_adapter_in_wiring()

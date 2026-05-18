# CellML Runtime

`biosim.contrib.cellml.LibCellMLBioModule` is the optional CellML equivalent of
`biosim.contrib.sbml.TelluriumSBMLBioModule`. It uses only open-source runtime
dependencies: libCellML for CellML parsing, validation, analysis, and Python code
generation, and SciPy/NumPy for numerical integration.

Install the optional runtime with:

```bash
pip install 'biosim[cellml]'
```

The base `biosim` package does not import `libcellml` or `scipy` at module import
time. They are loaded lazily when a CellML wrapper prepares or simulates a model.

## Architecture

The runtime prepares a CellML model in five steps:

1. Parse the `.cellml` file with `libcellml.Parser`.
2. Resolve and flatten imports with `libcellml.Importer` when the installed
   libCellML exposes importer support.
3. Validate with `libcellml.Validator`.
4. Analyse with `libcellml.Analyser`.
5. Generate Python code with a `GeneratorProfile.PYTHON` profile.

Generated Python is stored in a runtime cache, never in model repositories by
default. Cache keys are deterministic and include the CellML file content,
libCellML version, and Biosim adapter version. Override the cache location with
`BIOSIM_CELLML_CACHE`; otherwise Biosim uses the platform cache directory.

Simulation uses `scipy.integrate.solve_ivp`. The generated `compute_rates` or
`computeRates` function supplies the right-hand side, and generated
`compute_variables` or `computeVariables` computes algebraic variables at output
sample points.

## Wrapper Contract

CellML wrappers should be metadata subclasses:

```python
from biosim.contrib.cellml import LibCellMLBioModule


class SmallCellMLModel(LibCellMLBioModule):
    _CELLML_ID = "example:small"
    _TITLE = "Small CellML model"
    _OBSERVABLES = ["x"]
    _STATE_OUTPUT_ALIASES = {"x": "state_x"}
    _HEADLINE_OUTPUTS = {
        "mean_state_x": ("x", "dimensionless", "Mean state x over the recent window."),
    }

    def __init__(self, model_path: str = "data/small.cellml", integration_step: float = 0.1) -> None:
        super().__init__(model_path=model_path, integration_step=integration_step)
```

`model_path` resolves relative to the wrapper file's parent model directory,
matching the SBML wrapper convention:

```text
model/
  data/model.cellml
  src/wrapper.py
```

Public subclass fields:

- `_CELLML_ID`: stable upstream identifier.
- `_TITLE`: readable model title.
- `_OBSERVABLES`: generated state or algebraic variable names to publish.
- `_STATE_OUTPUT_ALIASES`: public output keys for generated names.
- `_PARAMETER_INPUTS`: named scalar inputs that override generated variables.
- `_INITIAL_CONDITION_INPUTS`: named scalar inputs that override generated
  initial state values.
- `_HEADLINE_OUTPUTS`: scalar headline outputs from observable trajectories.
- `_TIME_UNIT`: integration time unit label.
- `_STATE_OUTPUT_NAME`, `_SUMMARY_OUTPUT_NAME`: record output names.

If `_OBSERVABLES` is omitted, the runtime publishes state variables, capped by
`_MAX_DEFAULT_OBSERVABLES`.

## Outputs

Each wrapper publishes:

- `state`: latest selected state and algebraic observable values.
- `summary`: duration, observable count, largest change, and peak diagnostics.
- `variable_labels`: optional map from public keys to `component.variable`
  labels.
- configured scalar headline outputs.

These are dynamic scientific trajectories, not structural metadata summaries.

## Real PhysioMe Usage

For a PhysioMe model already checked into a model repository:

```python
from src.huang_ferrell_1996_huangferrell1996_model import HuangFerrell1996Huangferrell1996Model

model = HuangFerrell1996Huangferrell1996Model(
    model_path="data/huang_ferrell_1996.cellml",
    integration_step=0.01,
)
model.advance_window(0.0, 1.0)
print(model.get_outputs()["state"].value)
```

The model repository keeps the original CellML artifact and upstream metadata;
Biosim generates and caches executable code at runtime.

## Limitations

The first runtime version targets ODE CellML models supported by libCellML Python
code generation. Unsupported DAE systems, unresolved imports, invalid CellML,
analysis failures, generator failures, and solver failures raise
`CellMLRuntimeError` with stage-specific context.

OpenCOR is intentionally not a runtime dependency. Its CLI can be used later as a
validation or parity tool, but embeddable Biosim library code should depend on
libCellML and SciPy only.

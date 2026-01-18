# Biosimulant

A unified, modular biological simulation platform with a plugin-first architecture.

## Vision

Build a standard-agnostic simulation composition layer: wire reusable modules into a world, run them with an injected solver, and visualize/debug runs via a Python-declared UI (SimUI). Rather than re-implementing every biological standard in-core, the system should embrace adapters that wrap existing simulators/standards and expose them as `bsim` modules.

## Target Users

- **Near-term beachhead: Neuroscience** — Compose and visualize small neuron/microcircuit models with reproducible configs.
- **Developers building simulation tooling** — Want a composable runtime, wiring contracts, and a UI layer for experiments/demos.
- **Longer-term** — Other domains via domain packs and adapter packages (e.g., SBML/CellML tooling, PK/PD engines).

## Core Capabilities

### Multi-Scale Simulation Engine (`bsim`)
- **BioWorld** — Runtime container that orchestrates simulation steps, publishes lifecycle events, and routes directed module-to-module messages (biosignals)
- **BioModule** — Pluggable units of behavior with local state that can listen to global world events and exchange directed biosignals with peers
- **Solver** — Configurable execution strategies for time-stepping (fixed-step, adaptive, custom)
- **Wiring System** — Declarative module graph configuration via code, YAML, or TOML
- **Adapter-friendly** — External simulators can be wrapped as modules/solvers via plugins; core stays standard-agnostic

### Hybrid Execution
- Run simulations locally for development and testing
- Scale to cloud/HPC workloads for production and research

### Web-Based Interface (SimUI)
- Python-declared UI for controlling and visualizing simulations
- Built-in visualization types: time series, bar charts, tables, images, graphs
- Real-time event logging and status monitoring
- No frontend development required—declare UI components from Python

### Plugin SDK
- Open-source extensibility via robust plugin architecture
- Modules can declare input/output ports for connection validation
- Standard event lifecycle: `LOADED → BEFORE_SIMULATION → STEP × N → AFTER_SIMULATION`

## Standards Strategy (Adapter-First)

Instead of integrating CellML/NeuroML/SBML “directly” into core, build a stable set of `bsim` contracts so small Python packages can wrap existing runtimes:
- A wrapper package loads a standard model (e.g., NeuroML or SBML) using the best available runtime.
- The wrapper exposes that runtime as a `BioModule` (and/or `Solver`) with explicit ports/topics.
- The wrapper can provide visuals (raster plots, traces, tables) via the `VisualSpec` JSON contract.

This keeps `bsim` focused on composition, orchestration, and UX while letting domain ecosystems evolve independently.

## Beachhead Demo (Neuro)

Build a “stimulus → spikes” sandbox with a credible, reproducible tutorial:
- Single-neuron Izhikevich regimes (tonic spiking vs bursting) with Vm traces.
- Small E/I microcircuit under Poisson drive showing asynchronous irregular spiking (raster + population rate).
- Config-driven runs (YAML/TOML) defining modules + wiring + parameters.
- SimUI dashboard: controls for dt/steps/input rate/weights/seed; outputs for raster image, rate timeseries, Vm traces, and summary metrics table.

## Project Structure

```
Biosimulant/
├── B-Simulant/              # Core Python simulation library (bsim)
│   ├── src/bsim/            # Source code
│   ├── examples/            # Usage examples
│   ├── docs/                # API documentation
│   └── tests/               # Test suite
├── bsim-backend/            # FastAPI backend for web platform
│   └── app/                 # Application code
├── biosimulant-landing-page/# Marketing website (React/Vite)
│   └── src/                 # Frontend source
└── README.md                # This file
```

## Expected Features

### Core Simulation Engine
- [ ] Fixed-step and adaptive solvers
- [ ] FixedStepBioSolver with configurable bio-quantities (temperature, water, oxygen, etc.)
- [ ] Event-driven architecture with lifecycle hooks
- [ ] Directed biosignal routing between modules
- [ ] Connection validation via port declarations
- [ ] YAML/TOML configuration file support

### Built-in Modules (Planned)
- [ ] Molecular dynamics integration
- [ ] Cellular automata systems
- [ ] Metabolic pathway modeling
- [ ] Neural network simulation
- [ ] Population dynamics
- [ ] Pharmacokinetic/pharmacodynamic (PK/PD) modeling

### Web Platform
- [ ] User authentication and project management
- [ ] Simulation configuration and execution
- [ ] Real-time visualization dashboard
- [ ] Result storage and export
- [ ] Collaboration features
- [ ] API access for programmatic control

### SimUI Components
- [ ] Number inputs and sliders
- [ ] Buttons and action triggers
- [ ] Event log panels
- [ ] Visuals panel (charts, graphs, images)
- [ ] Parameter sweeps
- [ ] Batch execution controls

## Quick Start

### Installation

```bash
# Install the core library
pip install bsim

# For development
pip install -e './B-Simulant[dev]'

# With UI support
pip install -e './B-Simulant[ui]'
```

### Basic Usage

```python
import bsim

# Create a solver with bio-quantities
solver = bsim.FixedStepBioSolver(
    temperature=bsim.TemperatureParams(
        initial=300.0,          # Kelvin
        delta_per_step=1.0,
        rate_per_time=0.5,
        bounds=(273.15, 315.15)
    ),
    water=bsim.ScalarRateParams(name="water", initial=1.0, rate_per_time=-0.6),
    oxygen=bsim.ScalarRateParams(name="oxygen", initial=0.3, rate_per_time=-0.2),
)

# Create and run simulation
world = bsim.BioWorld(solver=solver)
result = world.simulate(steps=100, dt=0.1)
print(result)
```

### Custom Module Example

```python
class Eye(bsim.BioModule):
    def __init__(self):
        self.photons_seen = 0

    def subscriptions(self):
        return {bsim.BioWorldEvent.STEP}

    def outputs(self):
        return {"visual_stream"}

    def on_event(self, event, payload, world):
        self.photons_seen += 1
        world.publish_biosignal(self, "visual_stream", {"t": payload.get("t")})

# Wire modules together
world = bsim.BioWorld(solver=bsim.FixedStepSolver())
eye, lgn = Eye(), LGN()
world.add_biomodule(eye)
world.add_biomodule(lgn)
world.connect_biomodules(eye, "visual_stream", lgn)
world.simulate(steps=100, dt=0.1)
```

### Launch Web UI

```python
from bsim.simui import Interface, Number, Button, EventLog, VisualsPanel

world = bsim.BioWorld(solver=bsim.FixedStepSolver())
ui = Interface(
    world,
    controls=[Number("steps", 100), Number("dt", 0.1), Button("Run")],
    outputs=[EventLog(), VisualsPanel()]
)
ui.launch()  # Opens at http://127.0.0.1:7861/ui/
```

## Development

### Running Tests

```bash
cd B-Simulant
pytest
pytest --cov=bsim --cov-report=term-missing
```

## Architecture Principles

1. **Composability** — Build complex simulations from simple, reusable modules
2. **Extensibility** — Plugin-first design for custom solvers, modules, and visualizations
3. **Standards Compliance** — Compatible with major biological modeling standards
4. **Hybrid Execution** — Seamless transition from local to distributed computing
5. **Developer Experience** — Python-native API with minimal boilerplate

## Roadmap

### Phase 1: Core Engine (Current)
- Fixed-step solver with bio-quantities
- Module wiring and biosignal routing
- SimUI for basic visualization

### Phase 2: Web Platform
- User accounts and project management
- Cloud-based simulation execution
- Collaboration features

### Phase 3: Domain Modules
- Pre-built modules for common biological systems
- Integration with external databases (UniProt, PDB, etc.)
- Standard format import/export (SBML, CellML)

## Monetization (planned)

Open-source core (`bsim`) + paid hosted SimUI/run management:
- Hosted run history, sharing, permissions, and artifact storage (configs, events, visuals).
- Batch runs / parameter sweeps, comparisons, and reporting.
- Optional: adapters and domain packs remain open, while operational workflows are monetized.

### Phase 4: Advanced Features
- GPU acceleration
- Distributed simulation across clusters
- Machine learning integration
- Real-time optimization and parameter fitting

## License

MIT License

## Links

- Website: https://biosimulant.com
- Documentation: Coming soon
- Issues: GitHub Issues

# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Generic CLI runner for bsim simulations.

Run any YAML/TOML config directly without needing a separate demo script.

Usage:
    python -m bsim config.yaml                    # Run headless (print final state)
    python -m bsim config.yaml --simui            # Launch SimUI dashboard
    python -m bsim config.yaml --simui --port 8080
    python -m bsim config.yaml --steps 5000 --dt 0.05

YAML config format (extended):
    meta:
      title: "My Simulation"
      description: "Markdown description here"

      # Solver options (three formats supported):

      # 1. String shorthand
      solver: fixed           # or "default"

      # 2. Built-in solver with parameters
      solver:
        type: default
        temperature:
          initial: 20.0
          bounds: [0.0, 50.0]

      # 3. Custom solver class (from any installed package)
      solver:
        class: my_package.MySolver
        args:
          custom_param: 42

    # Modules - reference any importable class
    modules:
      my_module:
        class: some_package.CustomModule
        args:
          param: value

    wiring:
      - from: module_a.out.signal
        to: [module_b.in.signal]

Plugin Architecture:
    Any pip-installable package can provide custom modules and solvers.
    Reference them by their full dotted import path in YAML configs.

    Example:
        pip install bsim-neurolab

        # config.yaml
        meta:
          solver:
            class: bsim_neurolab.AdaptiveSolver
        modules:
          neuron:
            class: bsim_neurolab.HodgkinHuxley
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def load_config(path: Path) -> Dict[str, Any]:
    """Load YAML or TOML config file."""
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError:
            print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    elif suffix in {".toml", ".tml"}:
        try:
            import tomllib  # type: ignore
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                print("Error: TOML support requires Python 3.11+ or tomli. Install with: pip install tomli", file=sys.stderr)
                sys.exit(1)
        with path.open("rb") as f:
            return tomllib.load(f)
    else:
        print(f"Error: Unsupported config format: {suffix}", file=sys.stderr)
        sys.exit(1)


def _import_class(dotted_path: str) -> type:
    """Import a class from a dotted path like 'package.module.ClassName'."""
    from importlib import import_module

    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path or not class_name:
        raise ValueError(f"Invalid import path: {dotted_path}")
    module = import_module(module_path)
    return getattr(module, class_name)


def create_solver(solver_spec: Any, temp_override: Optional[float] = None) -> "Solver":
    """Create a solver from YAML spec.

    Supports three formats:
    1. String shorthand: "fixed" or "default"
    2. Dict with type: {type: "default", temperature: {initial: 20.0, bounds: [0, 50]}}
    3. Dict with class: {class: "my_package.MySolver", args: {...}}
    """
    import bsim
    from bsim.solver import Solver

    # Format 1: String shorthand
    if isinstance(solver_spec, str):
        if solver_spec == "default":
            from bsim.solver import FixedStepBioSolver, TemperatureParams

            initial_temp = temp_override if temp_override is not None else 25.0
            return FixedStepBioSolver(
                temperature=TemperatureParams(initial=initial_temp, bounds=(0.0, 50.0)),
            )
        return bsim.FixedStepSolver()

    # Format 2 & 3: Dict-based configuration
    if isinstance(solver_spec, dict):
        # Format 3: Custom class
        if "class" in solver_spec:
            try:
                cls = _import_class(solver_spec["class"])
            except Exception as e:
                print(f"Error importing solver class '{solver_spec['class']}': {e}", file=sys.stderr)
                sys.exit(1)

            args = solver_spec.get("args", {})
            if not isinstance(args, dict):
                args = {}

            try:
                return cls(**args)
            except Exception as e:
                print(f"Error instantiating solver '{solver_spec['class']}': {e}", file=sys.stderr)
                sys.exit(1)

        # Format 2: Built-in with parameters
        solver_type = solver_spec.get("type", "fixed")
        if solver_type == "default":
            from bsim.solver import FixedStepBioSolver, TemperatureParams

            temp_spec = solver_spec.get("temperature", {})
            if isinstance(temp_spec, dict):
                initial_temp = temp_override if temp_override is not None else temp_spec.get("initial", 25.0)
                bounds = temp_spec.get("bounds", [0.0, 50.0])
                if isinstance(bounds, list) and len(bounds) == 2:
                    bounds = tuple(bounds)
                else:
                    bounds = (0.0, 50.0)
                temp_params = TemperatureParams(initial=initial_temp, bounds=bounds)
            else:
                initial_temp = temp_override if temp_override is not None else 25.0
                temp_params = TemperatureParams(initial=initial_temp, bounds=(0.0, 50.0))

            return FixedStepBioSolver(temperature=temp_params)

        return bsim.FixedStepSolver()

    # Fallback: no solver spec or invalid
    return bsim.FixedStepSolver()


def create_world(config: Dict[str, Any], temp_override: Optional[float] = None) -> "BioWorld":
    """Create a BioWorld from config, using appropriate solver."""
    import bsim

    meta = config.get("meta", {})
    solver_spec = meta.get("solver", "fixed")

    solver = create_solver(solver_spec, temp_override=temp_override)
    world = bsim.BioWorld(solver=solver)
    return world


def run_headless(world: "BioWorld", steps: int, dt: float) -> None:
    """Run simulation without UI and print results."""
    print(f"Running simulation: {steps} steps, dt={dt}")
    print("-" * 40)

    world.simulate(steps=steps, dt=dt)

    print(f"Simulation complete.")
    print("-" * 40)

    # Print final visuals summary
    visuals = world.collect_visuals()
    if visuals:
        print(f"Collected visuals from {len(visuals)} module(s):")
        for entry in visuals:
            module_name = entry.get("module", "unknown")
            vis_list = entry.get("visuals", [])
            for v in vis_list:
                render_type = v.get("render", "unknown")
                print(f"  - {module_name}: {render_type}")
    else:
        print("No visuals collected.")


def run_simui(
    world: "BioWorld",
    config: Dict[str, Any],
    *,
    config_path: Path,
    steps: int,
    dt: float,
    port: int,
    host: str,
    open_browser: bool,
) -> None:
    """Launch SimUI with the configured world."""
    try:
        from bsim.simui import Interface, Number, Button, EventLog, VisualsPanel
    except ImportError as e:
        print(f"Error: SimUI requires additional dependencies: {e}", file=sys.stderr)
        print("Install with: pip install 'bsim[ui]' or pip install fastapi uvicorn", file=sys.stderr)
        sys.exit(1)

    meta = config.get("meta", {})
    title = meta.get("title", "BioSim Simulation")
    description = meta.get("description")

    # Build default controls
    controls = [
        Number("steps", steps, label="Steps", minimum=10, maximum=100000, step=10),
        Number("dt", dt, label="dt", minimum=0.001, maximum=1.0, step=0.01),
        Button("Run"),
    ]

    outputs = [
        EventLog(limit=100),
        VisualsPanel(refresh="auto", interval_ms=500),
    ]

    ui = Interface(
        world,
        title=title,
        description=description,
        controls=controls,
        outputs=outputs,
        config_path=config_path,
    )

    print(f"Starting SimUI: http://{host}:{port}/ui/")
    print("Press Ctrl+C to stop.")

    ui.launch(host=host, port=port, open_browser=open_browser)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m bsim",
        description="Run bsim simulations from YAML/TOML config files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m bsim examples/configs/ecology_predator_prey.yaml --simui
  python -m bsim config.yaml --steps 5000 --dt 0.05
  python -m bsim config.yaml --simui --port 8080 --open
        """,
    )

    parser.add_argument(
        "config",
        type=Path,
        help="Path to YAML or TOML config file",
    )
    parser.add_argument(
        "--simui",
        action="store_true",
        help="Launch SimUI web dashboard instead of headless run",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1000,
        help="Number of simulation steps (default: 1000)",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.1,
        help="Time step size (default: 0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="SimUI server port (default: 8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="SimUI server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="Open browser automatically when starting SimUI",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override initial temperature (for FixedStepBioSolver)",
    )

    args = parser.parse_args()

    # Validate config file exists
    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    # Load config
    config = load_config(args.config)

    # Create world with appropriate solver
    world = create_world(config, temp_override=args.temperature)

    # Load modules and wiring from config
    import bsim
    bsim.load_wiring(world, args.config)

    # Get module count for display
    try:
        module_count = len(world._biomodule_listeners)
    except Exception:
        module_count = 0

    print(f"Loaded config: {args.config}")
    print(f"Modules: {module_count}")

    if args.simui:
        run_simui(
            world,
            config,
            config_path=args.config.resolve(),
            steps=args.steps,
            dt=args.dt,
            port=args.port,
            host=args.host,
            open_browser=args.open_browser,
        )
    else:
        run_headless(world, steps=args.steps, dt=args.dt)


if __name__ == "__main__":
    main()

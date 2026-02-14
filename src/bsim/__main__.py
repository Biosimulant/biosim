# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Generic CLI runner for bsim simulations.

Run any YAML/TOML config directly without needing a separate demo script.

Usage:
    python -m bsim config.yaml                    # Run headless
    python -m bsim config.yaml --simui            # Launch SimUI dashboard
    python -m bsim config.yaml --duration 10.0

YAML config format (simplified):
    meta:
      title: "My Simulation"
      description: "Markdown description here"

    modules:
      my_module:
        class: some_package.CustomModule
        args:
          param: value
        min_dt: 0.1

    wiring:
      - from: module_a.signal
        to: [module_b.input]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict


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
    if suffix in {".toml", ".tml"}:
        try:
            import tomllib  # type: ignore
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                print(
                    "Error: TOML support requires Python 3.11+ or tomli. Install with: pip install tomli",
                    file=sys.stderr,
                )
                sys.exit(1)
        with path.open("rb") as f:
            return tomllib.load(f)
    print(f"Error: Unsupported config format: {suffix}", file=sys.stderr)
    sys.exit(1)


def create_world() -> "BioWorld":
    import bsim

    return bsim.BioWorld()


def run_headless(world: "BioWorld", duration: float, tick_dt: float | None) -> None:
    """Run simulation without UI and print results."""
    print(f"Running simulation: duration={duration}")
    print("-" * 40)

    world.run(duration=duration, tick_dt=tick_dt)

    print("Simulation complete.")
    print("-" * 40)

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
    duration: float,
    tick_dt: float | None,
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

    controls = [
        Number("duration", duration, label="Duration", minimum=0.01, maximum=100000.0, step=0.1),
        Number("tick_dt", tick_dt or 0.1, label="Tick dt", minimum=0.001, maximum=10.0, step=0.01),
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
  python -m bsim wiring.yaml --simui
  python -m bsim config.yaml --duration 10.0
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
        "--duration",
        type=float,
        default=10.0,
        help="Simulation duration in BioWorld time units (default: 10.0)",
    )
    parser.add_argument(
        "--tick",
        type=float,
        default=0.1,
        help="Tick interval for UI/events (default: 0.1)",
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

    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)

    world = create_world()

    import bsim
    bsim.load_wiring(world, args.config)

    try:
        module_count = len(world.module_names)
    except Exception:
        module_count = 0

    print(f"Loaded config: {args.config}")
    print(f"Modules: {module_count}")

    tick_dt = args.tick if args.tick > 0 else None

    if args.simui:
        run_simui(
            world,
            config,
            config_path=args.config.resolve(),
            duration=args.duration,
            tick_dt=tick_dt,
            port=args.port,
            host=args.host,
            open_browser=args.open_browser,
        )
    else:
        run_headless(world, duration=args.duration, tick_dt=tick_dt)


if __name__ == "__main__":
    main()

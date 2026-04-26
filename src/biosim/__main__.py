# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Generic CLI runner for biosim simulations.

Run any YAML/TOML config directly without needing a separate demo script.

Usage:
    python -m biosim config.yaml                    # Run headless
    python -m biosim config.yaml --simui            # Launch SimUI dashboard
    python -m biosim config.yaml --duration 10.0

YAML config format (simplified):
    meta:
      title: "My Simulation"
      description: "Markdown description here"

    modules:
      my_module:
        class: some_package.CustomModule
        args:
          param: value
    runtime:
      communication_step: 0.1

    wiring:
      - from: module_a.signal
        to: [module_b.input]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

from .pack import (
    PackageError,
    build_package,
    fetch_package,
    run_package,
    validate_package,
)


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


def create_world(config: Dict[str, Any] | None = None, communication_step: float | None = None) -> "BioWorld":
    import biosim

    config = config or {}
    runtime = config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
    step = communication_step if communication_step is not None else runtime.get("communication_step")
    if step is None:
        raise ValueError("runtime.communication_step is required")
    return biosim.BioWorld(communication_step=float(step))


def run_headless(world: "BioWorld", duration: float) -> None:
    """Run simulation without UI and print results."""
    print(f"Running simulation: duration={duration}")
    print("-" * 40)

    world.run(duration=duration)

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
    port: int,
    host: str,
    open_browser: bool,
) -> None:
    """Launch SimUI with the configured world."""
    try:
        from biosim.simui import Interface, Number, Button, EventLog, VisualsPanel
    except ImportError as e:
        print(f"Error: SimUI requires additional dependencies: {e}", file=sys.stderr)
        print("Install with: pip install 'biosim[ui]' or pip install fastapi uvicorn", file=sys.stderr)
        sys.exit(1)

    meta = config.get("meta", {})
    title = meta.get("title", "BioSim Simulation")
    description = meta.get("description")

    controls = [
        Number("duration", duration, label="Duration", minimum=0.01, maximum=100000.0, step=0.1),
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
    if len(sys.argv) > 1 and sys.argv[1] == "pack":
        _main_pack(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(
        prog="python -m biosim",
        description="Run biosim simulations from YAML/TOML config files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m biosim wiring.yaml --simui
  python -m biosim config.yaml --duration 10.0
  python -m biosim config.yaml --simui --port 8080 --open
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
        "--communication-step",
        type=float,
        default=None,
        help="Override runtime.communication_step from config",
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

    world = create_world(config, args.communication_step)

    import biosim
    biosim.load_wiring(world, args.config)

    try:
        module_count = len(world.module_names)
    except Exception:
        module_count = 0

    print(f"Loaded config: {args.config}")
    print(f"Modules: {module_count}")

    if args.simui:
        run_simui(
            world,
            config,
            config_path=args.config.resolve(),
            duration=args.duration,
            port=args.port,
            host=args.host,
            open_browser=args.open_browser,
        )
    else:
        run_headless(world, duration=args.duration)


def _main_pack(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m biosim pack",
        description="Build, validate, fetch, and run BioSim package files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print machine-readable JSON output instead of human-readable summaries",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build a model or self-contained lab package")
    build_parser.add_argument("source", type=Path)
    build_parser.add_argument("--out", type=Path, default=None)
    build_parser.add_argument("--package", dest="package_name", type=str, default=None)
    build_parser.add_argument("--version", type=str, default="0.1.0")
    build_parser.add_argument("--visibility", type=str, default="private")

    validate_parser = subparsers.add_parser("validate", help="Validate a .bsimpkg")
    validate_parser.add_argument("package_file", type=Path)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch a package into the local cache")
    fetch_parser.add_argument("reference", type=str, help="Reference in package@version form")

    run_parser = subparsers.add_parser("run", help="Run a model or lab package")
    run_parser.add_argument("package_file", type=Path)
    run_parser.add_argument("--no-install-deps", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            target = build_package(
                args.source,
                output_path=args.out,
                package_name=args.package_name,
                version=args.version,
                visibility=args.visibility,
            )
            validation = validate_package(target)
            _print_pack_result(
                args.json_output,
                {
                    "command": "build",
                    "package_file": str(target),
                    "valid": validation.valid,
                    "package": validation.metadata.get("package") if validation.metadata else None,
                    "version": validation.metadata.get("version") if validation.metadata else None,
                    "package_type": validation.metadata.get("package_type") if validation.metadata else None,
                    "warnings": validation.warnings,
                },
            )
            return
        if args.command == "validate":
            result = validate_package(args.package_file)
            if not result.valid:
                _print_validation_failure(args.package_file, result, json_output=args.json_output)
                raise SystemExit(1)
            _print_validation_success(args.package_file, result, json_output=args.json_output)
            return
        if args.command == "fetch":
            package_name, version = _parse_package_reference(args.reference)
            target = fetch_package(package_name, version)
            _print_pack_result(
                args.json_output,
                {
                    "command": "fetch",
                    "package": package_name,
                    "version": version,
                    "package_file": str(target),
                },
            )
            return
        if args.command == "run":
            result = run_package(args.package_file, install_deps=not args.no_install_deps)
            _print_run_result(args.package_file, result, json_output=args.json_output)
            return
    except PackageError as exc:
        _print_pack_error(exc, json_output=args.json_output)
        raise SystemExit(1) from exc


def _parse_package_reference(value: str) -> tuple[str, str]:
    package_name, sep, version = value.rpartition("@")
    if not sep or not package_name.strip() or not version.strip():
        raise PackageError("Package reference must be in package@version form")
    return package_name.strip(), version.strip()


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True)


def _print_pack_result(json_output: bool, payload: dict[str, Any]) -> None:
    if json_output:
        print(json_dumps(payload))
        return
    command = payload.get("command", "pack")
    print(f"BioSim package {command} succeeded.")
    if payload.get("package"):
        print(f"Package: {payload['package']}@{payload.get('version')}")
    if payload.get("package_type"):
        print(f"Type: {payload['package_type']}")
    if payload.get("package_file"):
        print(f"File: {payload['package_file']}")
    warnings = payload.get("warnings") or []
    for warning in warnings:
        print(f"Warning: {warning}")


def _print_validation_success(package_file: Path, result: Any, *, json_output: bool) -> None:
    payload = {
        "command": "validate",
        "package_file": str(package_file),
        "valid": True,
        "package": result.metadata.get("package") if result.metadata else None,
        "version": result.metadata.get("version") if result.metadata else None,
        "package_type": result.metadata.get("package_type") if result.metadata else None,
        "warnings": result.warnings,
        "metadata": result.metadata,
    }
    if json_output:
        print(json_dumps(payload))
        return
    print("BioSim package validation passed.")
    print(f"File: {package_file}")
    if result.metadata:
        print(f"Package: {result.metadata.get('package')}@{result.metadata.get('version')}")
        print(f"Type: {result.metadata.get('package_type')}")
    if result.warnings:
        for warning in result.warnings:
            print(f"Warning: {warning}")


def _print_validation_failure(package_file: Path, result: Any, *, json_output: bool) -> None:
    payload = {
        "command": "validate",
        "package_file": str(package_file),
        "valid": False,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
    }
    if json_output:
        print(json_dumps(payload), file=sys.stderr)
        return
    print("BioSim package validation failed.", file=sys.stderr)
    print(f"File: {package_file}", file=sys.stderr)
    for error in result.errors:
        print(f"Error: {error}", file=sys.stderr)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)


def _print_run_result(package_file: Path, result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json_dumps(result))
        return
    print("BioSim package run completed.")
    print(f"File: {package_file}")
    if result.get("package"):
        print(f"Package: {result['package']}@{result.get('version')}")
    if "outputs" in result:
        outputs = ", ".join(result.get("outputs") or [])
        print(f"Outputs: {outputs or '(none)'}")
    if "modules" in result:
        modules = ", ".join(
            f"{item.get('alias')}={item.get('path')}"
            for item in result.get("modules", [])
        )
        print(f"Resolved models: {modules or '(none)'}")
    if "duration" in result:
        print(f"Duration: {result['duration']}")


def _print_pack_error(exc: Exception, *, json_output: bool) -> None:
    payload = {"error": str(exc)}
    if json_output:
        print(json_dumps(payload), file=sys.stderr)
        return
    print("BioSim package command failed.", file=sys.stderr)
    print(f"Error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

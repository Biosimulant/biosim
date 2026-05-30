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
import tempfile
from pathlib import Path
from typing import Any, Dict

from .extensions import (
    ExtensionUnavailableError,
    extension_error_payload,
    get_extension_command_spec,
    is_extension_command_path,
    run_extension_command,
)
from .package_repo import build_package_repo, validate_package_repo
from .pack import (
    PACKAGE_EXTENSIONS,
    PackageError,
    build_package,
    fetch_package,
    prepare_lab_package,
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
        print("Install with: pip install 'biosimulant[ui]' or pip install fastapi uvicorn", file=sys.stderr)
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


def main(argv: list[str] | None = None, *, prog: str = "python -m biosim") -> None:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] == "pack":
        _main_pack(args_list[1:], prog=f"{prog} pack")
        return
    if args_list and args_list[0] == "packages":
        _main_packages(args_list[1:], prog=f"{prog} packages")
        return
    if args_list and args_list[0] == "labs":
        _main_labs(args_list[1:], prog=f"{prog} labs")
        return
    if args_list and is_extension_command_path(args_list[0]):
        _run_extension_or_exit(args_list[0], args_list[1:], prog=f"{prog} {args_list[0]}")
        return

    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run biosim simulations from YAML/TOML config files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {prog} labs init ./my-lab --name "My Lab"
  {prog} labs validate ./my-lab
  {prog} packages build biosimulant-packages.yaml
  {prog} wiring.yaml --simui
  {prog} config.yaml --duration 10.0
  {prog} config.yaml --simui --port 8080 --open
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

    args = parser.parse_args(args_list)

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


def _main_labs(argv: list[str], *, prog: str = "python -m biosim labs") -> None:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Initialize, validate, run, and serve local Biosimulant labs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a local runnable lab")
    init_parser.add_argument("path", type=Path, nargs="?", default=Path("."))
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--description", default=None)
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--empty", action="store_true", help="Create only lab.yaml without a starter model")
    init_parser.add_argument("--json", action="store_true", dest="json_output")

    validate_parser = subparsers.add_parser("validate", help="Validate a local lab source tree or .bsilab")
    validate_parser.add_argument("lab", type=Path, nargs="?", default=Path("."))
    validate_parser.add_argument("--json", action="store_true", dest="json_output")

    run_parser = subparsers.add_parser("run", help="Run a local lab source tree or .bsilab")
    run_parser.add_argument("lab", type=Path, nargs="?", default=Path("."))
    run_parser.add_argument("--no-install-deps", action="store_true")
    run_parser.add_argument("--results-file", type=Path, default=None)
    run_parser.add_argument("--json", action="store_true", dest="json_output")

    serve_parser = subparsers.add_parser("serve", help="Serve a local lab through SimUI")
    serve_parser.add_argument("lab", type=Path, nargs="?", default=Path("."))
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--open", action="store_true", dest="open_browser")
    serve_parser.add_argument("--no-install-deps", action="store_true")
    serve_parser.add_argument("--json", action="store_true", dest="json_output")

    for name in (
        "list",
        "get",
        "create",
        "import",
        "pull",
        "save",
        "rename",
        "delete",
        "open",
        "vendor-model",
        "change-model",
        "inspect-owned",
        "add-model",
        "export",
        "publish",
    ):
        _add_extension_subcommand(subparsers, name, f"labs {name}")

    args = parser.parse_args(argv)
    if extension_command := getattr(args, "extension_command_path", None):
        _run_extension_or_exit(extension_command, argv, prog=prog)
        return

    try:
        if args.command == "init":
            payload = _init_lab_project(
                args.path,
                name=args.name,
                description=args.description,
                force=args.force,
                empty=args.empty,
            )
            _print_lab_init_success(payload, json_output=args.json_output)
            return
        if args.command == "validate":
            result = _validate_local_lab(args.lab)
            if not result.valid:
                _print_validation_failure(args.lab, result, json_output=args.json_output)
                raise SystemExit(1)
            _print_lab_validation_success(args.lab, result, json_output=args.json_output)
            return
        if args.command == "run":
            package_file = _package_file_for_lab(args.lab)
            result = run_package(package_file, install_deps=not args.no_install_deps)
            if args.results_file:
                args.results_file.parent.mkdir(parents=True, exist_ok=True)
                args.results_file.write_text(json_dumps(result) + "\n", encoding="utf-8")
            _print_run_result(package_file, result, json_output=args.json_output)
            return
        if args.command == "serve":
            package_file = _package_file_for_lab(args.lab)
            prepared = prepare_lab_package(package_file, install_deps=not args.no_install_deps)
            meta = {
                "title": prepared.manifest.get("title") or prepared.package,
                "description": prepared.manifest.get("description"),
            }
            if args.json_output:
                print(
                    json_dumps(
                        {
                            "command": "serve",
                            "package": prepared.package,
                            "version": prepared.version,
                            "url": f"http://{args.host}:{args.port}/ui/",
                            "modules": prepared.modules,
                        }
                    )
                )
            run_simui(
                prepared.world,
                {"meta": meta},
                config_path=_lab_config_path(args.lab),
                duration=prepared.duration,
                port=args.port,
                host=args.host,
                open_browser=args.open_browser,
            )
            return
    except PackageError as exc:
        _print_pack_error(exc, json_output=getattr(args, "json_output", False))
        raise SystemExit(1) from exc


def _main_packages(argv: list[str], *, prog: str = "python -m biosim packages") -> None:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Validate/build package repositories and run local package archives.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a package repo manifest or package archive")
    validate_parser.add_argument("target", type=Path)
    validate_parser.add_argument("--json", action="store_true", dest="json_output")

    build_parser = subparsers.add_parser("build", help="Build packages declared in a repo manifest")
    build_parser.add_argument("manifest", type=Path)
    build_parser.add_argument("--out", type=Path, default=Path("dist/biosimulant-packages"))
    build_parser.add_argument("--json", action="store_true", dest="json_output")

    run_parser = subparsers.add_parser("run", help="Run a local .bsimodel or .bsilab package")
    run_parser.add_argument("package_file", type=Path)
    run_parser.add_argument("--no-install-deps", action="store_true")
    run_parser.add_argument("--json", action="store_true", dest="json_output")

    for name in ("preview", "import", "export-model", "export-lab", "publish", "ci"):
        _add_extension_subcommand(subparsers, name, f"packages {name}")

    args = parser.parse_args(argv)
    if extension_command := getattr(args, "extension_command_path", None):
        _run_extension_or_exit(extension_command, argv, prog=prog)
        return

    try:
        if args.command == "validate":
            if args.target.suffix in PACKAGE_EXTENSIONS:
                result = validate_package(args.target)
                if not result.valid:
                    _print_validation_failure(args.target, result, json_output=args.json_output)
                    raise SystemExit(1)
                _print_validation_success(args.target, result, json_output=args.json_output)
                return
            manifest = validate_package_repo(args.target)
            _print_package_repo_validation_success(manifest, json_output=args.json_output)
            return
        if args.command == "build":
            built = build_package_repo(args.manifest, args.out)
            _print_package_repo_build_success(built, json_output=args.json_output)
            return
        if args.command == "run":
            result = run_package(args.package_file, install_deps=not args.no_install_deps)
            _print_run_result(args.package_file, result, json_output=args.json_output)
            return
    except PackageError as exc:
        _print_pack_error(exc, json_output=getattr(args, "json_output", False))
        raise SystemExit(1) from exc


def _main_pack(argv: list[str], *, prog: str = "python -m biosim pack") -> None:
    parser = argparse.ArgumentParser(
        prog=prog,
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

    validate_parser = subparsers.add_parser("validate", help="Validate a model or lab package")
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


def _init_lab_project(
    path: Path,
    *,
    name: str,
    description: str | None,
    force: bool,
    empty: bool,
) -> dict[str, Any]:
    target = path.expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise PackageError(f"Lab path must be a directory: {target}")
    if target.exists() and not force and any(target.iterdir()):
        raise PackageError(
            f"Lab path is not empty: {target}. Re-run with --force to write lab files."
        )
    target.mkdir(parents=True, exist_ok=True)

    slug = _slugify(name)
    if empty:
        models_block = "models: []\nchildren: []\nwiring: []"
    else:
        _write_starter_model(target / "models" / "hello")
        models_block = """models:
  - path: models/hello
    alias: hello
children: []
wiring: []"""

    lab_yaml = f"""schema_version: "2.0"
title: {_yaml_string(name)}
description: {_yaml_string(description) if description is not None else "null"}
package: local/{slug}
version: 0.1.0
{models_block}
runtime:
  communication_step: 1.0
  duration: 1.0
  initial_inputs: {{}}
"""
    (target / "lab.yaml").write_text(lab_yaml, encoding="utf-8")
    return {
        "created": True,
        "path": str(target),
        "manifest": str(target / "lab.yaml"),
        "starter_model": None if empty else str(target / "models" / "hello"),
    }


def _write_starter_model(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "model.yaml").write_text(
        """schema_version: "2.0"
title: "Hello Model"
description: "Starter local Biosimulant model"
standard: other
tags: [starter]
authors: ["Biosimulant"]
package: local/hello
version: 0.1.0
biosim:
  entrypoint: "src.hello:HelloModule"
  communication_step: 1.0
""",
        encoding="utf-8",
    )
    src_dir = path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "hello.py").write_text(
        '''from biosim import BioModule, ScalarSignal, SignalSpec


class HelloModule(BioModule):
    def __init__(self):
        self.time = 0.0

    def outputs(self):
        return {"time": SignalSpec.scalar(dtype="float64")}

    def advance_window(self, _start, end):
        self.time = float(end)

    def get_outputs(self):
        spec = self.outputs()["time"]
        return {
            "time": ScalarSignal(
                source="hello",
                name="time",
                value=self.time,
                emitted_at=self.time,
                spec=spec,
            )
        }

    def snapshot(self):
        return {"time": self.time}
''',
        encoding="utf-8",
    )


def _validate_local_lab(path: Path) -> Any:
    return validate_package(_package_file_for_lab(path))


def _package_file_for_lab(path: Path) -> Path:
    target = path.expanduser().resolve()
    if target.is_file():
        if target.suffix != ".bsilab":
            raise PackageError(f"Expected a .bsilab package: {target}")
        return target
    if not target.is_dir():
        raise PackageError(f"Lab path not found: {target}")
    _lab_config_path(target)
    temp_dir = Path(tempfile.mkdtemp(prefix="biosim-lab-"))
    return build_package(target, output_path=temp_dir / f"{target.name or 'lab'}.bsilab")


def _lab_config_path(path: Path) -> Path:
    target = path.expanduser().resolve()
    if target.is_file():
        return target
    for name in ("lab.yaml", "lab.yml"):
        manifest = target / name
        if manifest.is_file():
            return manifest
    raise PackageError(f"Could not find lab.yaml or lab.yml in {target}")


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "lab"


def _yaml_string(value: str) -> str:
    import json

    return json.dumps(value)


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True)


def _add_extension_subcommand(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    command_path: str,
) -> None:
    spec = get_extension_command_spec(command_path)
    summary = spec.summary if spec else "Product extension command"
    parser = subparsers.add_parser(name, help=f"{summary} (requires product extension)")
    parser.add_argument("extension_args", nargs=argparse.REMAINDER)
    parser.set_defaults(extension_command_path=command_path)


def _run_extension_or_exit(command: str, argv: list[str], *, prog: str) -> None:
    try:
        exit_code = run_extension_command(command, argv, prog=prog)
    except ExtensionUnavailableError as exc:
        _print_extension_unavailable(exc, json_output="--json" in argv)
        raise SystemExit(1) from exc
    if exit_code:
        raise SystemExit(exit_code)


def _print_extension_unavailable(exc: ExtensionUnavailableError, *, json_output: bool) -> None:
    if json_output:
        print(json_dumps(extension_error_payload(exc)), file=sys.stderr)
        return

    payload = extension_error_payload(exc)
    print("Biosimulant product extension required.", file=sys.stderr)
    print(f"Command: {payload['invocation']}", file=sys.stderr)
    print(f"Category: {payload['category']}", file=sys.stderr)
    print(f"Extension: {payload['extension']}", file=sys.stderr)
    print(f"Reason: {payload['summary']}", file=sys.stderr)
    print(f"Next step: {payload['install_hint']}", file=sys.stderr)
    print(
        "Open-source local commands remain available: "
        "biosimulant labs init|validate|run|serve; "
        "biosimulant packages validate|build|run.",
        file=sys.stderr,
    )


def _print_lab_init_success(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json_dumps(payload))
        return
    print("Biosimulant lab initialized.")
    print(f"Path: {payload['path']}")
    print(f"Manifest: {payload['manifest']}")
    if payload.get("starter_model"):
        print(f"Starter model: {payload['starter_model']}")


def _print_lab_validation_success(package_file: Path, result: Any, *, json_output: bool) -> None:
    payload = {
        "command": "labs.validate",
        "lab": str(package_file),
        "valid": True,
        "package": result.metadata.get("package") if result.metadata else None,
        "version": result.metadata.get("version") if result.metadata else None,
        "warnings": result.warnings,
        "metadata": result.metadata,
    }
    if json_output:
        print(json_dumps(payload))
        return
    print("Biosimulant lab validation passed.")
    print(f"Lab: {package_file}")
    if result.metadata:
        print(f"Package: {result.metadata.get('package')}@{result.metadata.get('version')}")
    for warning in result.warnings:
        print(f"Warning: {warning}")


def _print_package_repo_validation_success(manifest: Any, *, json_output: bool) -> None:
    payload = {
        "command": "packages.validate",
        "manifest": str(manifest.path),
        "valid": True,
        "package_count": len(manifest.packages),
        "packages": [
            {
                "package": entry.package,
                "version": entry.version,
                "package_type": entry.package_type,
                "path": entry.path.as_posix(),
                "visibility": entry.visibility,
            }
            for entry in manifest.packages
        ],
    }
    if json_output:
        print(json_dumps(payload))
        return
    print("Biosimulant package manifest validation passed.")
    print(f"Manifest: {manifest.path}")
    print(f"Packages: {len(manifest.packages)}")
    for entry in manifest.packages:
        print(f"  - {entry.package}@{entry.version} ({entry.package_type})")


def _print_package_repo_build_success(built: list[dict[str, Any]], *, json_output: bool) -> None:
    payload = {"command": "packages.build", "built": built}
    if json_output:
        print(json_dumps(payload))
        return
    print("Biosimulant package manifest build succeeded.")
    print(f"Built packages: {len(built)}")
    for entry in built:
        print(
            f"  - {entry['package']}@{entry['version']} "
            f"({entry['package_type']}): {entry['path']}"
        )


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

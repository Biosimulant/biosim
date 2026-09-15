"""The `biosimulant compatibility` commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from .compatibility import (
    CompatibilitySupportUnavailable,
    _standard,
    build_lock,
    load_yaml,
    normalize_manifest,
    validate_manifest,
)

# Port direction in a selector -> (role in `compare`, port kind).
_PORT_ROLES = {"outputs": ("source", "output"), "inputs": ("target", "input")}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Check whether model ports can connect, using the Biosimulant Model "
            "Compatibility Standard."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Check the compatibility block in a model.yaml")
    validate.add_argument("manifest", type=Path, help="Path to model.yaml")

    normalize = commands.add_parser(
        "normalize", help="Print a model.yaml's compatibility data in normalized JSON form"
    )
    normalize.add_argument("manifest", type=Path, help="Path to model.yaml")
    normalize.add_argument(
        "--output", type=Path, help="Write the JSON to this file instead of printing it"
    )

    compare = commands.add_parser(
        "compare", help="Check whether an output port can feed an input port"
    )
    compare.add_argument(
        "producer", metavar="SOURCE", help="Output port, e.g. model.yaml#outputs.concentration"
    )
    compare.add_argument(
        "consumer", metavar="TARGET", help="Input port, e.g. model.yaml#inputs.dose"
    )

    profiles = commands.add_parser("profiles", help="List or show compatibility profiles")
    profile_commands = profiles.add_subparsers(dest="profiles_command", required=True)
    list_profiles = profile_commands.add_parser("list", help="List the available profiles")
    list_profiles.add_argument("--domain", help="Only list profiles in this domain, e.g. core")
    show_profile = profile_commands.add_parser("show", help="Print one profile's full definition")
    show_profile.add_argument("profile_ref", help="Profile ref (a URL), as shown by `profiles list`")

    lock = commands.add_parser("lock", help="Write compatibility.lock.json for a model")
    lock.add_argument("manifest", type=Path, help="Path to model.yaml")
    lock.add_argument(
        "--output",
        type=Path,
        default=Path("compatibility.lock.json"),
        help="Where to write the lock file (default: compatibility.lock.json)",
    )

    plan = commands.add_parser(
        "plan", help="Check every wiring connection in a lab and print a plan"
    )
    plan.add_argument("lab", type=Path, help="Path to lab.yaml, or the folder that contains it")
    plan.add_argument(
        "--policy",
        type=Path,
        help="JSON file with the compatibility policy that decides which connections are allowed",
    )
    plan.add_argument(
        "--capabilities",
        type=Path,
        help="JSON file listing adapter or inference capabilities that can convert data between ports",
    )
    plan.add_argument(
        "--output", type=Path, help="Write the plan to this file instead of printing it"
    )

    commands.add_parser("conformance", help="Run the standard's conformance tests")
    return parser


def _select_port(selector: str, expected_direction: str) -> tuple[dict[str, Any] | None, list[str]]:
    role, kind = _PORT_ROLES[expected_direction]
    if "#" not in selector:
        raise ValueError(
            "Point to a port like model.yaml#outputs.concentration or "
            f"model.yaml#inputs.dose (got {selector!r})"
        )
    path_text, fragment = selector.rsplit("#", 1)
    direction, separator, name = fragment.partition(".")
    if not separator or direction != expected_direction or not name:
        raise ValueError(
            f"The {role} must be an {kind} port: PATH#{expected_direction}.PORT (got {selector!r})"
        )
    manifest = load_yaml(path_text)
    for port in manifest.get("io", {}).get(direction, []):
        if port.get("name") == name:
            contract = port.get("contract")
            return contract, list(contract.get("profile_refs", [])) if isinstance(contract, dict) else []
    raise ValueError(f"No {kind} port named {name!r} in {path_text}")


def _read_json(path: Path) -> Any:
    data = path.read_bytes()
    if len(data) > 4 * 1024 * 1024:
        raise ValueError(f"{path} is larger than the 4 MiB safety limit")
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


def _local_lab_plan(
    path: Path,
    policy_path: Path | None,
    capabilities_path: Path | None,
) -> dict[str, Any]:
    standard = _standard()
    lab_path = path / "lab.yaml" if path.is_dir() else path
    lab = load_yaml(lab_path)
    root = lab_path.parent
    models: dict[str, dict[str, Any]] = {}
    for entry in lab.get("models", []):
        alias, model_path = entry.get("alias"), entry.get("path")
        if isinstance(alias, str) and isinstance(model_path, str):
            candidate = (root / model_path).resolve()
            manifest_path = candidate / "model.yaml" if candidate.is_dir() else candidate
            models[alias] = load_yaml(manifest_path)

    def port(ref: str, direction: str) -> tuple[dict[str, Any] | None, list[str]]:
        alias, separator, name = ref.rpartition(".")
        if not separator or alias not in models:
            return None, []
        for item in models[alias].get("io", {}).get(direction, []):
            if item.get("name") == name:
                contract = item.get("contract")
                return contract, list(contract.get("profile_refs", [])) if isinstance(contract, dict) else []
        return None, []

    policy = _read_json(policy_path) if policy_path else {}
    capabilities = _read_json(capabilities_path) if capabilities_path else []
    if not isinstance(policy, dict):
        raise ValueError("The --policy file must contain a JSON object")
    if not isinstance(capabilities, list) or not all(isinstance(item, dict) for item in capabilities):
        raise ValueError("The --capabilities file must contain a JSON array of objects")

    reports = []
    materialized_nodes: list[dict[str, Any]] = []
    materialized_edges: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = [
        {"kind": "lab", "sha256": standard.digest(lab)},
        {"kind": "standard-bundle", "sha256": standard.get_bundle().digest},
    ]
    decisions: list[str] = []
    for edge_index, edge in enumerate(lab.get("wiring", [])):
        source_ref = edge.get("from")
        if not isinstance(source_ref, str):
            continue
        source, source_refs = port(source_ref, "outputs")
        raw_targets = edge.get("to", [])
        targets = [raw_targets] if isinstance(raw_targets, str) else raw_targets
        for target_ref in targets:
            if not isinstance(target_ref, str):
                continue
            target, target_refs = port(target_ref, "inputs")
            resolution = standard.resolve_contracts(
                source,
                target,
                capabilities,
                policy=policy,
            )
            report = resolution["report"]
            reports.append(
                {
                    "edge_index": edge_index,
                    "source": source_ref,
                    "target": target_ref,
                    "report": report,
                    "resolution": resolution["resolution"],
                }
            )
            if resolution["resolution"] == "RESOLVED":
                edge_plan = resolution["plan"]
                prefix = f"edge-{edge_index}-{len(reports)}"
                for node in edge_plan["nodes"]:
                    materialized_nodes.append({**node, "id": f"{prefix}-{node['id']}"})
                for plan_edge in edge_plan["edges"]:
                    materialized_edges.append(
                        {
                            **plan_edge,
                            "from": f"{prefix}-{plan_edge['from']}",
                            "to": f"{prefix}-{plan_edge['to']}",
                            "source_port": source_ref,
                            "target_port": target_ref,
                        }
                    )
                references.extend(edge_plan.get("immutable_references", []))
                decisions.append(edge_plan["policy"]["decision"])
            else:
                decisions.append("BLOCK")
    decision = (
        "BLOCK"
        if "BLOCK" in decisions
        else "APPROVAL_REQUIRED"
        if "APPROVAL_REQUIRED" in decisions
        else "ALLOW"
    )
    plan_without_digest = {
        "schema_version": "0.1",
        "standard": "https://biosimulant.com/standards/model-compatibility/v0.1",
        "bundle_sha256": standard.get_bundle().digest,
        "nodes": materialized_nodes,
        "edges": materialized_edges,
        "reports": reports,
        "policy": {
            "decision": decision,
            "digest": standard.digest(policy),
            "rules": policy,
        },
        "approvals": [],
        "immutable_references": references,
    }
    result = {**plan_without_digest, "digest": standard.digest(plan_without_digest)}
    findings = standard.validate_object(result, "resolution-plan.schema.json")
    if findings:
        raise ValueError(
            "Internal error: the generated plan failed schema validation: "
            + "; ".join(item.message for item in findings)
        )
    return result


def _conformance() -> dict[str, Any]:
    standard = _standard()
    bundle = standard.get_bundle()
    bundle.verify_integrity()
    profiles = bundle.catalogue["profiles"]
    passed = 0
    for summary in profiles:
        fixture = bundle.read_json(f"fixtures/profiles/{summary['domain']}/{summary['name']}.json")
        profile_ref = fixture["profile_ref"]
        positive, negative, unknown = fixture["cases"]
        if standard.validate_contract(positive["contract"], [profile_ref]):
            raise ValueError(f"Conformance failed for {profile_ref}: valid example was rejected")
        negative_findings = standard.validate_contract(negative["contract"], [profile_ref])
        if not any(item.reason_code == negative["reason_code"] for item in negative_findings):
            raise ValueError(
                f"Conformance failed for {profile_ref}: invalid example was not rejected "
                f"with {negative['reason_code']}"
            )
        report = standard.compare_contracts(unknown["source"], unknown["target"], target_profile_refs=[profile_ref])
        if report["status"] != "UNKNOWN":
            raise ValueError(
                f"Conformance failed for {profile_ref}: expected UNKNOWN, got {report['status']}"
            )
        passed += 3
    return {
        "valid": True,
        "release": bundle.manifest["release"],
        "profiles": len(profiles),
        "profile_fixtures_passed": passed,
        "bundle_sha256": bundle.digest,
        "ga_ready": bool(bundle.manifest.get("ga_ready", False)),
        "ga_blockers": list(bundle.manifest.get("ga_blockers", [])),
    }


def _error_message(exc: Exception) -> str:
    if isinstance(exc, OSError) and exc.filename is not None and exc.strerror:
        return f"{exc.filename}: {exc.strerror}"
    if isinstance(exc, yaml.YAMLError):
        return f"invalid YAML: {exc}"
    return str(exc)


def main(argv: list[str], *, prog: str = "biosimulant compatibility") -> None:
    args = _parser(prog).parse_args(argv)
    try:
        _run(args, prog=prog)
    except (ValueError, OSError, yaml.YAMLError, CompatibilitySupportUnavailable) as exc:
        print(f"error: {_error_message(exc)}", file=sys.stderr)
        raise SystemExit(2) from exc


def _run(args: argparse.Namespace, *, prog: str) -> None:
    if args.command == "validate":
        manifest = load_yaml(args.manifest)
        findings = validate_manifest(manifest)
        print(_json({"valid": not findings, "opted_in": "compatibility" in manifest, "findings": findings}))
        if findings:
            raise SystemExit(1)
        return
    if args.command == "normalize":
        result = normalize_manifest(load_yaml(args.manifest))
        content = _json(result) + "\n"
        if args.output:
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
        return
    if args.command == "compare":
        source, source_refs = _select_port(args.producer, "outputs")
        target, target_refs = _select_port(args.consumer, "inputs")
        print(_json(_standard().compare_contracts(source, target, source_profile_refs=source_refs, target_profile_refs=target_refs)))
        return
    if args.command == "profiles":
        bundle = _standard().get_bundle()
        if args.profiles_command == "show":
            try:
                profile = bundle.profile(args.profile_ref)
            except KeyError:
                raise ValueError(
                    f"Unknown profile {args.profile_ref!r}. "
                    f"Run `{prog} profiles list` to see available profiles."
                ) from None
            print(_json(profile))
        else:
            profiles = bundle.catalogue["profiles"]
            if args.domain:
                profiles = [profile for profile in profiles if profile["domain"] == args.domain]
            print(_json({"count": len(profiles), "profiles": profiles}))
        return
    if args.command == "lock":
        result = build_lock(load_yaml(args.manifest))
        if result is None:
            raise ValueError(
                f"{args.manifest} has no `compatibility` block, so there's nothing to lock"
            )
        args.output.write_text(_json(result) + "\n", encoding="utf-8")
        print(_json({"output": str(args.output), "digest": result["digest"]}))
        return
    if args.command == "plan":
        result = _local_lab_plan(args.lab, args.policy, args.capabilities)
        content = _json(result) + "\n"
        if args.output:
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
        return
    if args.command == "conformance":
        print(_json(_conformance()))

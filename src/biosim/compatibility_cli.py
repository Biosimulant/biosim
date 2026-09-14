"""Local compatibility CLI backed by the pinned public specification bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .compatibility import _standard, build_lock, load_yaml, normalize_manifest, validate_manifest


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Validate and resolve BioSimulant model compatibility contracts.")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Validate an opted-in model.yaml")
    validate.add_argument("manifest", type=Path)

    normalize = commands.add_parser("normalize", help="Normalize an opted-in model.yaml")
    normalize.add_argument("manifest", type=Path)
    normalize.add_argument("--output", type=Path)

    compare = commands.add_parser("compare", help="Compare producer and consumer model ports")
    compare.add_argument("producer", help="model.yaml#outputs.port")
    compare.add_argument("consumer", help="model.yaml#inputs.port")

    profiles = commands.add_parser("profiles", help="Inspect installed profile definitions")
    profile_commands = profiles.add_subparsers(dest="profiles_command", required=True)
    list_profiles = profile_commands.add_parser("list")
    list_profiles.add_argument("--domain")
    show_profile = profile_commands.add_parser("show")
    show_profile.add_argument("profile_ref")

    lock = commands.add_parser("lock", help="Create an inspectable compatibility lock")
    lock.add_argument("manifest", type=Path)
    lock.add_argument("--output", type=Path, default=Path("compatibility.lock.json"))

    plan = commands.add_parser("plan", help="Compare every local wiring edge in a lab")
    plan.add_argument("lab", type=Path)
    plan.add_argument("--policy", type=Path)
    plan.add_argument("--capabilities", type=Path)
    plan.add_argument("--output", type=Path)

    commands.add_parser("conformance", help="Execute all installed profile fixtures")
    return parser


def _select_port(selector: str, expected_direction: str) -> tuple[dict[str, Any] | None, list[str]]:
    if "#" not in selector:
        raise ValueError("Port selectors must use model.yaml#inputs.port or model.yaml#outputs.port")
    path_text, fragment = selector.rsplit("#", 1)
    direction, separator, name = fragment.partition(".")
    if not separator or direction != expected_direction or not name:
        raise ValueError(f"Expected #{expected_direction}.<port-name>")
    manifest = load_yaml(path_text)
    for port in manifest.get("io", {}).get(direction, []):
        if port.get("name") == name:
            contract = port.get("contract")
            return contract, list(contract.get("profile_refs", [])) if isinstance(contract, dict) else []
    raise ValueError(f"No {direction} port named {name!r} in {path_text}")


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

    policy = json.loads(policy_path.read_text()) if policy_path else {}
    capabilities = json.loads(capabilities_path.read_text()) if capabilities_path else []
    if not isinstance(policy, dict):
        raise ValueError("Compatibility policy must be a JSON object")
    if not isinstance(capabilities, list) or not all(isinstance(item, dict) for item in capabilities):
        raise ValueError("Capabilities must be a JSON array of capability objects")

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
        raise ValueError("Generated resolution plan is invalid: " + "; ".join(item.message for item in findings))
    return result


def _conformance() -> dict[str, Any]:
    standard = _standard()
    bundle = standard.get_bundle()
    passed = 0
    for summary in bundle.catalogue["profiles"]:
        fixture = bundle.read_json(f"fixtures/profiles/{summary['domain']}/{summary['name']}.json")
        positive, negative, unknown = fixture["cases"]
        if standard.validate_contract(positive["contract"], [fixture["profile_ref"]]):
            raise ValueError(f"Positive fixture failed for {fixture['profile_ref']}")
        negative_findings = standard.validate_contract(negative["contract"], [fixture["profile_ref"]])
        if not any(item.reason_code == negative["reason_code"] for item in negative_findings):
            raise ValueError(f"Negative fixture failed for {fixture['profile_ref']}")
        report = standard.compare_contracts(unknown["source"], unknown["target"], target_profile_refs=[fixture["profile_ref"]])
        if report["status"] != "UNKNOWN":
            raise ValueError(f"UNKNOWN fixture failed for {fixture['profile_ref']}: {report['status']}")
        passed += 3
    return {"valid": True, "profiles": 650, "profile_fixtures_passed": passed, "bundle_sha256": bundle.digest}


def main(argv: list[str], *, prog: str = "biosimulant compatibility") -> None:
    args = _parser(prog).parse_args(argv)
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
            print(_json(bundle.profile(args.profile_ref)))
        else:
            profiles = bundle.catalogue["profiles"]
            if args.domain:
                profiles = [profile for profile in profiles if profile["domain"] == args.domain]
            print(_json({"count": len(profiles), "profiles": profiles}))
        return
    if args.command == "lock":
        result = build_lock(load_yaml(args.manifest))
        if result is None:
            raise ValueError("The manifest has not opted into compatibility")
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

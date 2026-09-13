from __future__ import annotations

from biosim.execution_capabilities import (
    declared_execution_requirements,
    evaluate_local_execution_capability,
)


def _host(*, cores: int = 8, memory_mb: int = 16_384, cuda=None, mps: bool = False):
    return {
        "platform": {"system": "TestOS", "machine": "test64"},
        "cpu": {"logical_cores": cores, "memory_mb": memory_mb},
        "accelerators": {
            "cuda": {"available": bool(cuda), "devices": cuda or [], "probe": "test"},
            "mps": {"available": mps, "devices": [], "probe": "test"},
        },
    }


def test_cpu_lab_is_supported_when_declared_resources_fit() -> None:
    manifest = {"runtime": {"cpu_cores": 4, "memory_mb": 4096}, "models": []}

    result = evaluate_local_execution_capability(manifest, host=_host())

    assert result["local_supported"] is True
    assert result["selected_backend"] == "cpu"
    assert result["requirements"]["requires_gpu"] is False
    assert result["blockers"] == []


def test_resource_shortfall_blocks_local_execution() -> None:
    manifest = {"hardware": {"cpu_cores": 12, "memory_gb": 32}}

    result = evaluate_local_execution_capability(
        manifest, host=_host(cores=8, memory_mb=16_384)
    )

    assert result["local_supported"] is False
    assert {item["code"] for item in result["blockers"]} == {
        "insufficient_cpu",
        "insufficient_memory",
    }


def test_exact_cuda_device_requirement_is_not_downgraded_to_any_gpu() -> None:
    manifest = {
        "models": [{"alias": "predictor", "parameters": {"accelerator": "a100"}}]
    }

    wrong_gpu = evaluate_local_execution_capability(
        manifest,
        host=_host(cuda=[{"name": "NVIDIA T4", "memory_mb": 16_384}]),
    )
    matching_gpu = evaluate_local_execution_capability(
        manifest,
        host=_host(cuda=[{"name": "NVIDIA A100-SXM4-80GB", "memory_mb": 81_920}]),
    )

    assert wrong_gpu["local_supported"] is False
    assert wrong_gpu["blockers"][0]["code"] == "accelerator_unavailable"
    assert matching_gpu["local_supported"] is True
    assert matching_gpu["selected_backend"] == "cuda"

    gpu_prefixed = evaluate_local_execution_capability(
        {"hardware": {"gpu_type": "gpu-t4"}},
        host=_host(cuda=[{"name": "NVIDIA T4", "memory_mb": 16_384}]),
    )
    assert gpu_prefixed["local_supported"] is True


def test_nested_accelerator_and_memory_requirements_are_detected_generically() -> None:
    manifest = {
        "children": [
            {
                "runtime": {"device": "mps"},
                "models": [{"hardware": {"memory_mb": 2048}}],
            }
        ]
    }

    requirements = declared_execution_requirements(manifest)

    assert requirements == {
        "accelerators": ["mps"],
        "requires_gpu": True,
        "cpu_cores": None,
        "memory_mb": 2048,
    }

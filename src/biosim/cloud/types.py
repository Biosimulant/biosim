"""Public value objects returned by the managed Biosimulant client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled", "timed_out"})


@dataclass(frozen=True)
class Artifact:
    id: str
    role: str | None = None
    file_name: str | None = None
    content_type: str | None = None
    format: str | None = None
    size_bytes: int | None = None
    status: str | None = None
    download_url: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Artifact":
        return cls(
            id=str(value.get("id") or value.get("artifact_id") or ""),
            role=value.get("role"),
            file_name=value.get("file_name"),
            content_type=value.get("content_type"),
            format=value.get("format"),
            size_bytes=value.get("size_bytes"),
            status=value.get("status"),
            download_url=value.get("download_url"),
        )


@dataclass(frozen=True)
class RunResult:
    run_id: str
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunResult":
        return cls(
            run_id=str(value.get("run_id") or ""),
            outputs=dict(value.get("outputs") or {}),
            artifacts=[Artifact.from_dict(item) for item in value.get("artifacts") or []],
            provenance=dict(value.get("provenance") or {}),
        )

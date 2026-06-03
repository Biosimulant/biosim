"""Source-neutral runtime data structures.

This module is provisional. The names are public for cross-runtime parity work,
but their exact shape may change in the next minor release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass
class LabTreePort:
    name: str
    maps_to: str


@dataclass
class LabTreeIO:
    inputs: Sequence[LabTreePort] = field(default_factory=tuple)
    outputs: Sequence[LabTreePort] = field(default_factory=tuple)


@dataclass
class LabTreeWire:
    from_ref: str
    to_refs: Sequence[str]


@dataclass
class LabTreeModel:
    alias: str
    ref: Mapping[str, Any] | Any | None = None
    parameters: Mapping[str, Any] | None = None


@dataclass
class LabTreeChild:
    alias: str
    tree: "LabTree | None" = None
    io: LabTreeIO | None = None


@dataclass
class LabTree:
    models: Sequence[LabTreeModel] = field(default_factory=tuple)
    wiring: Sequence[LabTreeWire] = field(default_factory=tuple)
    children: list[LabTreeChild] = field(default_factory=list)
    io: LabTreeIO = field(default_factory=LabTreeIO)


@dataclass(frozen=True)
class FlattenedLab:
    models: list[dict[str, Any]]
    wiring: list[dict[str, Any]]

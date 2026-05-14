"""Provisional runtime helpers shared by Biosim execution surfaces.

The ``biosim.runtime`` package centralizes kernel-level package interpretation:
entrypoint loading, typed initial-input coercion, communication-step resolution,
and source-neutral lab flattening. It is public but provisional for this minor
release; import these helpers from ``biosim.runtime`` rather than top-level
``biosim``.
"""

from __future__ import annotations

from .coercion import coerce_typed_inputs
from .entrypoint import flush_package_cache, load_entrypoint
from .flatten import flatten_lab_tree, lab_io_from_mapping
from .runtime_config import extract_communication_step, extract_settle_steps
from .types import (
    FlattenedLab,
    LabTree,
    LabTreeChild,
    LabTreeIO,
    LabTreeModel,
    LabTreePort,
    LabTreeWire,
)

__all__ = [
    "FlattenedLab",
    "LabTree",
    "LabTreeChild",
    "LabTreeIO",
    "LabTreeModel",
    "LabTreePort",
    "LabTreeWire",
    "coerce_typed_inputs",
    "extract_communication_step",
    "extract_settle_steps",
    "flatten_lab_tree",
    "flush_package_cache",
    "lab_io_from_mapping",
    "load_entrypoint",
]

# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING

from .__about__ import __version__
from .world import BioWorld, WorldEvent
from .modules import BioModule
from .signals import (
    AcceptedSignalProfile,
    ArraySignal,
    BioSignal,
    EventSignal,
    RecordSignal,
    ScalarSignal,
    SignalSpec,
    validate_connection_specs,
    validate_port_spec_direction,
)
from .visuals import VisualSpec, validate_visual_spec, normalize_visuals
from .wiring import (
    WiringBuilder,
    build_from_spec,
    load_wiring,
    load_wiring_toml,
    load_wiring_yaml,
)
from .pack import (
    build_package,
    export_lab_package,
    fetch_package,
    publish_package,
    run_package,
    unpack_package,
    validate_package,
)

if TYPE_CHECKING:  # pragma: no cover
    from . import simui as simui

__all__ = [
    "__version__",
    "BioWorld",
    "WorldEvent",
    "VisualSpec",
    "validate_visual_spec",
    "normalize_visuals",
    "BioModule",
    "BioSignal",
    "AcceptedSignalProfile",
    "ScalarSignal",
    "ArraySignal",
    "RecordSignal",
    "EventSignal",
    "SignalSpec",
    "validate_connection_specs",
    "validate_port_spec_direction",
    "WiringBuilder",
    "build_from_spec",
    "load_wiring",
    "load_wiring_toml",
    "load_wiring_yaml",
    "build_package",
    "export_lab_package",
    "fetch_package",
    "publish_package",
    "run_package",
    "unpack_package",
    "validate_package",
    "OnnxClassifierModule",
]


def __getattr__(name: str) -> ModuleType:
    # Lazily import optional namespaces so `import biosim` does not require extras.
    if name == "simui":
        return importlib.import_module(".simui", __name__)
    if name == "onnx":
        return importlib.import_module(".onnx", __name__)
    if name == "OnnxClassifierModule":
        return getattr(importlib.import_module(".onnx", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*__all__, "onnx", "simui"])

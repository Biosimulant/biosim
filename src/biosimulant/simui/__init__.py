# SPDX-FileCopyrightText: 2026-present Biosimulant Team
#
# SPDX-License-Identifier: MIT
"""Biosimulant SimUI namespace."""
from __future__ import annotations

import importlib
import sys

_simui = importlib.import_module("biosim.simui")
sys.modules[__name__] = _simui

for _name in ("build", "editor_api", "graph", "interface", "registry", "runner"):
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(f"biosim.simui.{_name}")

del _name

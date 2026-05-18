#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Run the optional libCellML-backed CellML runtime examples.

Install optional dependencies first:

    pip install 'biosim[cellml]'

Run the bundled fixture:

    python examples/cellml_runtime_example.py small

Run a real PhysioMe CellML file:

    python examples/cellml_runtime_example.py physiome /path/to/model.cellml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from biosim.contrib.cellml import CellMLRuntimeError, LibCellMLBioModule


class SmallDecayModel(LibCellMLBioModule):
    _CELLML_ID = "example:small_decay"
    _TITLE = "Small exponential decay CellML model"
    _OBSERVABLES = ["x"]
    _PARAMETER_INPUTS = {
        "decay_rate": (
            "k",
            1.0,
            "per_second",
            "First-order decay rate.",
        )
    }

    def __init__(self, integration_step: float = 0.1) -> None:
        super().__init__(
            model_path="examples/data/small_decay.cellml",
            integration_step=integration_step,
        )


class PhysioMeCellMLModel(LibCellMLBioModule):
    _CELLML_ID = "physiome:external"
    _TITLE = "External PhysioMe CellML model"
    _OBSERVABLES = None


def _run(model: LibCellMLBioModule, duration: float) -> dict[str, object]:
    model.advance_window(0.0, duration)
    outputs = model.get_outputs()
    return {
        "state": outputs[model._STATE_OUTPUT_NAME].value,
        "summary": outputs[model._SUMMARY_OUTPUT_NAME].value,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("small", "physiome"))
    parser.add_argument("cellml_path", nargs="?", help="Real PhysioMe .cellml path for the physiome example")
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--step", type=float, default=0.1)
    args = parser.parse_args(argv)

    if args.kind == "small":
        model: LibCellMLBioModule = SmallDecayModel(integration_step=args.step)
    else:
        if not args.cellml_path:
            parser.error("physiome example requires a CellML file path")
        path = Path(args.cellml_path).expanduser().resolve()
        if not path.exists():
            parser.error(f"CellML file does not exist: {path}")
        model = PhysioMeCellMLModel(str(path), integration_step=args.step)

    try:
        print(json.dumps(_run(model, args.duration), indent=2, sort_keys=True))
    except CellMLRuntimeError as exc:
        print(f"CellML runtime error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

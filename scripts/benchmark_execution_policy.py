#!/usr/bin/env python3
"""Repeatable microbenchmarks for the 0.0.26 execution dispatcher.

Run this file against the working tree and an archived pre-change tree with
``--legacy-only`` to measure the 10,000-window compatibility-path regression.
The canonical dispatcher sample is available only in runtimes that export
``ExecutionContext`` and ``ExecutionPolicy``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any

import biosim


class NoOpTemporal(biosim.BioModule):
    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self) -> dict[str, biosim.BioSignal]:
        return {}


def legacy_world_sample(windows: int) -> float:
    world = biosim.BioWorld(communication_step=1.0)
    world.add_biomodule("legacy", NoOpTemporal())
    started = time.perf_counter()
    world.run(float(windows))
    return time.perf_counter() - started


def percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, int(len(ordered) * 0.95) - 1)]


def canonical_dispatch_sample(iterations: int) -> dict[str, float] | None:
    if not hasattr(biosim, "ExecutionContext"):
        return None

    class CanonicalNoOp(biosim.BioModule):
        execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

        def outputs(self):
            return {"value": biosim.SignalSpec.scalar(dtype="float64")}

        def execute(self, inputs, *, context):
            return {"value": 1.0}

    world = biosim.BioWorld(communication_step=1.0)
    world.add_biomodule("canonical", CanonicalNoOp())
    world.setup()
    entry = world._modules["canonical"]  # Deliberately benchmarks the private dispatcher.
    context = biosim.ExecutionContext(
        policy=biosim.ExecutionPolicy.EACH_WINDOW,
        run_start=0.0,
        run_end=1.0,
        window_start=0.0,
        window_end=1.0,
    )
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        world._execute_module("canonical", entry, {}, context)
        samples.append((time.perf_counter_ns() - started) / 1_000.0)
    return {
        "iterations": iterations,
        "median_us": statistics.median(samples),
        "p95_us": percentile_95(samples),
        "max_us": max(samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=int, default=10_000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--dispatcher-iterations", type=int, default=20_000)
    parser.add_argument("--legacy-only", action="store_true")
    parser.add_argument("--baseline-json")
    parser.add_argument("--assert-thresholds", action="store_true")
    args = parser.parse_args()
    if args.windows <= 0 or args.repeats <= 0 or args.dispatcher_iterations <= 0:
        parser.error("window, repeat, and dispatcher counts must be positive")

    legacy_samples = [legacy_world_sample(args.windows) for _ in range(args.repeats)]
    result: dict[str, Any] = {
        "runtime_version": getattr(biosim, "__version__", "unknown"),
        "legacy_world": {
            "windows": args.windows,
            "repeats": args.repeats,
            "median_seconds": statistics.median(legacy_samples),
            "min_seconds": min(legacy_samples),
            "max_seconds": max(legacy_samples),
        },
    }
    if not args.legacy_only:
        result["canonical_dispatch"] = canonical_dispatch_sample(args.dispatcher_iterations)

    if args.baseline_json:
        with open(args.baseline_json, encoding="utf-8") as handle:
            baseline = json.load(handle)
        baseline_seconds = float(baseline["legacy_world"]["median_seconds"])
        regression = (result["legacy_world"]["median_seconds"] / baseline_seconds) - 1.0
        result["legacy_world"]["baseline_median_seconds"] = baseline_seconds
        result["legacy_world"]["regression_fraction"] = regression

    print(json.dumps(result, indent=2, sort_keys=True))

    if args.assert_thresholds:
        regression = result["legacy_world"].get("regression_fraction")
        if regression is None:
            parser.error("--assert-thresholds requires --baseline-json")
        if regression > 0.10:
            raise SystemExit(f"legacy 10,000-window regression {regression:.2%} exceeds 10%")
        dispatch = result.get("canonical_dispatch")
        if dispatch is not None and dispatch["p95_us"] > 50.0:
            raise SystemExit(
                f"canonical dispatcher p95 {dispatch['p95_us']:.2f} us exceeds 50 us"
            )


if __name__ == "__main__":
    main()

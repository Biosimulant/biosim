"""Runtime configuration helpers shared by Biosim execution surfaces."""

from __future__ import annotations

from typing import Any, Mapping


def _raise(
    error_cls: type[Exception], message: str, cause: BaseException | None = None
) -> None:
    error = error_cls(message)
    if cause is not None:
        raise error from cause
    raise error


def extract_communication_step(
    sim_cfg: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    *,
    fallback: float | int | str | None = None,
    error_cls: type[Exception] = RuntimeError,
) -> float:
    """Resolve the effective communication step using platform precedence."""

    runtime = runtime if isinstance(runtime, Mapping) else {}
    sim_cfg = sim_cfg if isinstance(sim_cfg, Mapping) else {}
    runtime_override = (
        sim_cfg.get("runtime") if isinstance(sim_cfg.get("runtime"), Mapping) else {}
    )

    raw_value = runtime_override.get("communication_step")
    if raw_value is None:
        raw_value = sim_cfg.get("communication_step")
    if raw_value is None:
        raw_value = runtime.get("communication_step")
    if raw_value is None:
        raw_value = fallback
    if raw_value is None:
        _raise(error_cls, "communication_step is required")

    try:
        communication_step = float(raw_value)
    except (TypeError, ValueError) as exc:
        _raise(error_cls, "communication_step must be numeric", exc)
    if communication_step <= 0:
        _raise(error_cls, "communication_step must be positive")
    return communication_step

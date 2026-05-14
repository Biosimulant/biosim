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


def extract_settle_steps(
    sim_cfg: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    *,
    fallback: int | float | str | None = 0,
    error_cls: type[Exception] = RuntimeError,
) -> int:
    """Resolve optional final graph propagation turns using platform precedence."""

    runtime = runtime if isinstance(runtime, Mapping) else {}
    sim_cfg = sim_cfg if isinstance(sim_cfg, Mapping) else {}
    runtime_override = (
        sim_cfg.get("runtime") if isinstance(sim_cfg.get("runtime"), Mapping) else {}
    )

    raw_value = runtime_override.get("settle_steps")
    if raw_value is None:
        raw_value = sim_cfg.get("settle_steps")
    if raw_value is None:
        raw_value = runtime.get("settle_steps")
    if raw_value is None:
        raw_value = fallback
    if raw_value is None:
        raw_value = 0

    if isinstance(raw_value, bool):
        _raise(error_cls, "settle_steps must be an integer")
    try:
        if isinstance(raw_value, float):
            if not raw_value.is_integer():
                _raise(error_cls, "settle_steps must be an integer")
            settle_steps = int(raw_value)
        elif isinstance(raw_value, int):
            settle_steps = raw_value
        elif isinstance(raw_value, str):
            stripped = raw_value.strip()
            if not stripped:
                _raise(error_cls, "settle_steps must be an integer")
            settle_steps = int(stripped, 10)
        else:
            _raise(error_cls, "settle_steps must be an integer")
    except ValueError as exc:
        _raise(error_cls, "settle_steps must be an integer", exc)

    if settle_steps < 0:
        _raise(error_cls, "settle_steps must be non-negative")
    return settle_steps

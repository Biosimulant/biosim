try:
    from .interface import Interface, Number, Button, EventLog, VisualsPanel
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency path
    # Provide a clear error when a stale/minimal environment lacks UI deps.
    missing = getattr(exc, "name", None)
    if missing in {"fastapi", "starlette", "uvicorn"}:
        raise ImportError(
            "SimUI dependencies are missing from this environment. "
            "Current biosimulant releases include SimUI by default. "
            "Reinstall with `pipx install biosimulant --force`; for older pipx installs, "
            "run `pipx inject biosimulant fastapi uvicorn`."
        ) from exc
    raise

__all__ = [
    "Interface",
    "Number",
    "Button",
    "EventLog",
    "VisualsPanel",
]

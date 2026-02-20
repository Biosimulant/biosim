try:
    from .interface import Interface, Number, Button, EventLog, VisualsPanel
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency path
    # Provide a clear error when UI extras aren't installed.
    missing = getattr(exc, "name", None)
    if missing in {"fastapi", "starlette", "uvicorn"}:
        raise ImportError(
            "SimUI requires optional UI dependencies. Install with `pip install 'biosim[ui]'`."
        ) from exc
    raise

__all__ = [
    "Interface",
    "Number",
    "Button",
    "EventLog",
    "VisualsPanel",
]

"""Canonical entrypoint loading for packaged Biosimulant models.

This module is provisional. It exists to keep CLI, desktop, and sandbox
entrypoint semantics aligned while namespace-package layouts are common.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def _raise(
    error_cls: type[Exception] | None, message: str, cause: BaseException | None = None
) -> None:
    if error_cls is None:
        if cause is not None:
            raise cause
        raise RuntimeError(message)
    error = error_cls(message)
    if cause is not None:
        raise error from cause
    raise error


def flush_package_cache(package_name: str) -> None:
    prefix = package_name + "."
    stale = [
        key for key in sys.modules if key == package_name or key.startswith(prefix)
    ]
    for key in stale:
        del sys.modules[key]


def _split_entrypoint(
    entrypoint: str, error_cls: type[Exception] | None
) -> tuple[str, str]:
    try:
        if ":" in entrypoint:
            module_path, attr = entrypoint.split(":", 1)
        else:
            module_path, attr = entrypoint.rsplit(".", 1)
    except ValueError as exc:
        _raise(error_cls, f"Invalid entrypoint: {entrypoint}", exc)
    if not module_path or not attr:
        _raise(error_cls, f"Invalid entrypoint: {entrypoint}")
    return module_path, attr


def load_entrypoint(
    entrypoint: str,
    *,
    model_path: str | os.PathLike[str] | None = None,
    error_cls: type[Exception] | None = RuntimeError,
) -> Any:
    """Load ``entrypoint`` with model-local file-spec loading when possible."""

    module_path, attr = _split_entrypoint(str(entrypoint), error_cls)
    top_package = module_path.split(".")[0]

    if model_path:
        model_path_str = str(Path(model_path))
        if model_path_str in sys.path:
            sys.path.remove(model_path_str)
        sys.path.insert(0, model_path_str)
        flush_package_cache(top_package)

        file_path = Path(model_path_str) / (module_path.replace(".", os.sep) + ".py")
        if file_path.is_file():
            spec = importlib.util.spec_from_file_location(module_path, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_path] = module
                try:
                    spec.loader.exec_module(module)
                except Exception as exc:
                    _raise(
                        error_cls,
                        f"Failed to import module '{module_path}': {exc}",
                        exc,
                    )
                try:
                    return getattr(module, attr)
                except AttributeError as exc:
                    _raise(
                        error_cls, f"Entrypoint attribute not found: {entrypoint}", exc
                    )

    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        _raise(error_cls, f"Failed to import module '{module_path}': {exc}", exc)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        _raise(error_cls, f"Entrypoint attribute not found: {entrypoint}", exc)

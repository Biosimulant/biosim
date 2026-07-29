# SPDX-FileCopyrightText: 2026-present Biosimulant Team
#
# SPDX-License-Identifier: MIT
"""Registry-scoped credential storage for the headless Biosimulant CLI."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


DEFAULT_REGISTRY = "hub.biosimulant.ai"
DEFAULT_HUB_API_BASE = "https://prod-api.biosimulant.com/api"
TOKEN_ENV = "BIOSIMULANT_TOKEN"
WORKSPACE_TOKEN_ENV = "BIOSIMULANT_WORKSPACE_TOKEN"
LEGACY_ACCESS_TOKEN_ENV = "BIOSIMULANT_ACCESS_TOKEN"
LEGACY_REFRESH_TOKEN_ENV = "BIOSIMULANT_REFRESH_TOKEN"
CREDENTIAL_HELPER_ENV = "BIOSIMULANT_CREDENTIAL_HELPER"
CREDENTIALS_FILE_ENV = "BIOSIMULANT_CREDENTIALS_FILE"
DISABLE_KEYRING_ENV = "BIOSIMULANT_DISABLE_KEYRING"
_KEYRING_SERVICE = "biosimulant-registry"
_WORKSPACE_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


class CredentialError(RuntimeError):
    """Raised when registry credentials cannot be read or persisted safely."""


def normalize_registry_origin(value: str | None) -> str:
    """Return a stable HTTPS registry origin without credentials or a path."""

    raw = (value or DEFAULT_REGISTRY).strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CredentialError(f"Invalid registry origin: {value}")
    if parsed.username or parsed.password:
        raise CredentialError("Registry origins must not contain credentials")
    host = parsed.hostname.lower()
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme.lower()}://{host}"


def credentials_file() -> Path:
    configured = os.environ.get(CREDENTIALS_FILE_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".config" / "biosimulant" / "credentials.json"


def resolve_token(registry: str | None = None) -> str | None:
    """Resolve a token using operation env, helper, keyring, then secure file."""

    value = os.environ.get(TOKEN_ENV, "").strip()
    if value:
        return value
    origin = normalize_registry_origin(registry)
    workspace_token = os.environ.get(WORKSPACE_TOKEN_ENV, "").strip()
    if workspace_token:
        return _exchange_workspace_token(origin, workspace_token)
    if origin == normalize_registry_origin(DEFAULT_REGISTRY):
        legacy_access = os.environ.get(LEGACY_ACCESS_TOKEN_ENV, "").strip()
        if legacy_access:
            return legacy_access
        legacy_refresh = os.environ.get(LEGACY_REFRESH_TOKEN_ENV, "").strip()
        if legacy_refresh:
            return _exchange_legacy_refresh_token(origin, legacy_refresh)
    helper_value = _helper_get(origin)
    if helper_value:
        return helper_value
    keyring_value = _keyring_get(origin)
    if keyring_value:
        return keyring_value
    return _file_credentials().get(origin)


def store_token(registry: str | None, token: str) -> str:
    origin = normalize_registry_origin(registry)
    secret = token.strip()
    if not secret:
        raise CredentialError("Token must not be empty")
    if _helper_store(origin, secret) or _keyring_store(origin, secret):
        return origin
    values = _file_credentials()
    values[origin] = secret
    _write_file_credentials(values)
    return origin


def delete_token(registry: str | None) -> bool:
    origin = normalize_registry_origin(registry)
    removed = _helper_delete(origin) or _keyring_delete(origin)
    values = _file_credentials()
    if origin in values:
        del values[origin]
        _write_file_credentials(values)
        removed = True
    return removed


def credential_status(registry: str | None) -> dict[str, Any]:
    origin = normalize_registry_origin(registry)
    source = None
    if os.environ.get(TOKEN_ENV, "").strip():
        source = "environment"
    elif os.environ.get(WORKSPACE_TOKEN_ENV, "").strip():
        source = "workspace"
    elif (
        origin == normalize_registry_origin(DEFAULT_REGISTRY)
        and os.environ.get(LEGACY_ACCESS_TOKEN_ENV, "").strip()
    ):
        source = "legacy_environment"
    elif _helper_get(origin):
        source = "credential_helper"
    elif _keyring_get(origin):
        source = "keyring"
    elif _file_credentials().get(origin):
        source = "file"
    return {"registry": origin, "authenticated": source is not None, "source": source}


def _file_credentials() -> dict[str, str]:
    path = credentials_file()
    if not path.exists():
        return {}
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if os.name != "nt" and mode & 0o077:
            raise CredentialError(
                f"Credential file permissions are too broad ({mode:o}); run chmod 600 {path}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
    except CredentialError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialError(f"Could not read credential file: {path}") from exc
    registries = payload.get("registries") if isinstance(payload, dict) else None
    if not isinstance(registries, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in registries.items()
        if isinstance(key, str) and isinstance(value, str) and value
    }


def _write_file_credentials(values: dict[str, str]) -> None:
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "registries": values}, handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def _keyring_module() -> Any | None:
    if os.environ.get(DISABLE_KEYRING_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None
    try:
        import keyring  # type: ignore
    except ImportError:
        return None
    return keyring


def _keyring_get(origin: str) -> str | None:
    module = _keyring_module()
    if module is None:
        return None
    try:
        return module.get_password(_KEYRING_SERVICE, origin)
    except Exception:
        return None


def _keyring_store(origin: str, token: str) -> bool:
    module = _keyring_module()
    if module is None:
        return False
    try:
        module.set_password(_KEYRING_SERVICE, origin, token)
        return True
    except Exception:
        return False


def _keyring_delete(origin: str) -> bool:
    module = _keyring_module()
    if module is None:
        return False
    try:
        module.delete_password(_KEYRING_SERVICE, origin)
        return True
    except Exception:
        return False


def _helper(action: str, origin: str, token: str | None = None) -> subprocess.CompletedProcess[str] | None:
    command = os.environ.get(CREDENTIAL_HELPER_ENV, "").strip()
    if not command:
        return None
    request = {"action": action, "registry": origin}
    if token is not None:
        request["token"] = token
    try:
        return subprocess.run(
            [command],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _helper_get(origin: str) -> str | None:
    completed = _helper("get", origin)
    if completed is None or completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    token = payload.get("token") if isinstance(payload, dict) else None
    return token if isinstance(token, str) and token else None


def _helper_store(origin: str, token: str) -> bool:
    completed = _helper("store", origin, token)
    return completed is not None and completed.returncode == 0


def _helper_delete(origin: str) -> bool:
    completed = _helper("delete", origin)
    return completed is not None and completed.returncode == 0


def _exchange_workspace_token(origin: str, identity_token: str) -> str:
    cached = _WORKSPACE_TOKEN_CACHE.get(origin)
    now = time.monotonic()
    if cached is not None and cached[1] > now:
        return cached[0]
    endpoint = os.environ.get("BIOSIMULANT_WORKSPACE_TOKEN_EXCHANGE_URL", "").strip()
    if not endpoint:
        endpoint = (
            f"{DEFAULT_HUB_API_BASE}/registry/v1/auth/exchange"
            if origin == normalize_registry_origin(DEFAULT_REGISTRY)
            else f"{origin}/api/registry/v1/auth/exchange"
        )
    body = json.dumps({"registry": origin}).encode("utf-8")
    request = Request(endpoint, data=body, method="POST")
    request.add_header("Authorization", f"Bearer {identity_token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise CredentialError("Workspace registry token exchange failed") from exc
    access_token = payload.get("accessToken") if isinstance(payload, dict) else None
    expires_in = payload.get("expiresIn", 300) if isinstance(payload, dict) else 300
    if not isinstance(access_token, str) or not access_token:
        raise CredentialError("Workspace registry token exchange returned no access token")
    try:
        ttl = max(1, min(300, int(expires_in)))
    except (TypeError, ValueError):
        ttl = 300
    _WORKSPACE_TOKEN_CACHE[origin] = (access_token, now + max(1, ttl - 30))
    return access_token


def _exchange_legacy_refresh_token(origin: str, refresh_token: str) -> str:
    cache_key = f"{origin}#legacy-refresh"
    cached = _WORKSPACE_TOKEN_CACHE.get(cache_key)
    now = time.monotonic()
    if cached is not None and cached[1] > now:
        return cached[0]
    endpoint = os.environ.get("BIOSIMULANT_TOKEN_ENDPOINT", "").strip()
    if not endpoint:
        endpoint = (
            f"{DEFAULT_HUB_API_BASE}/users/refresh"
            if origin == normalize_registry_origin(DEFAULT_REGISTRY)
            else f"{origin}/api/users/refresh"
        )
    body = json.dumps({"token": refresh_token}).encode("utf-8")
    request = Request(endpoint, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise CredentialError("Legacy Hub token refresh failed") from exc
    access_token = (
        payload.get("accessToken") or payload.get("access_token")
        if isinstance(payload, dict)
        else None
    )
    expires_in = (
        payload.get("expiresIn", payload.get("expires_in", 300))
        if isinstance(payload, dict)
        else 300
    )
    if not isinstance(access_token, str) or not access_token:
        raise CredentialError("Legacy Hub token refresh returned no access token")
    try:
        ttl = max(1, min(3600, int(expires_in)))
    except (TypeError, ValueError):
        ttl = 300
    _WORKSPACE_TOKEN_CACHE[cache_key] = (
        access_token,
        now + max(1, ttl - 30),
    )
    return access_token

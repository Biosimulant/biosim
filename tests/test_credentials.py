from __future__ import annotations

import json
from biosim import credentials


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_workspace_identity_is_exchanged_not_used_as_registry_bearer(
    monkeypatch,
    tmp_path,
) -> None:
    requests = []
    monkeypatch.setenv(credentials.WORKSPACE_TOKEN_ENV, "workspace-identity")
    monkeypatch.setenv(credentials.CREDENTIALS_FILE_ENV, str(tmp_path / "credentials.json"))
    monkeypatch.setenv(credentials.DISABLE_KEYRING_ENV, "1")
    credentials._WORKSPACE_TOKEN_CACHE.clear()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response({"accessToken": "operation-token", "expiresIn": 300})

    monkeypatch.setattr(credentials, "urlopen", fake_urlopen)
    assert credentials.resolve_token("hub.biosimulant.ai") == "operation-token"
    assert requests[0][0].get_header("Authorization") == "Bearer workspace-identity"
    assert requests[0][0].full_url == (
        f"{credentials.DEFAULT_HUB_API_BASE}/registry/v1/auth/exchange"
    )
    assert credentials.resolve_token("hub.biosimulant.ai") == "operation-token"
    assert len(requests) == 1


def test_legacy_default_hub_access_token_remains_usable(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(credentials.TOKEN_ENV, raising=False)
    monkeypatch.delenv(credentials.WORKSPACE_TOKEN_ENV, raising=False)
    monkeypatch.setenv(credentials.LEGACY_ACCESS_TOKEN_ENV, "legacy-token")
    monkeypatch.setenv(credentials.CREDENTIALS_FILE_ENV, str(tmp_path / "credentials.json"))
    monkeypatch.setenv(credentials.DISABLE_KEYRING_ENV, "1")

    assert credentials.resolve_token("hub.biosimulant.ai") == "legacy-token"
    assert credentials.credential_status("hub.biosimulant.ai")["source"] == "legacy_environment"


def test_legacy_refresh_token_is_exchanged_without_becoming_bearer(
    monkeypatch,
    tmp_path,
) -> None:
    requests = []
    monkeypatch.delenv(credentials.TOKEN_ENV, raising=False)
    monkeypatch.delenv(credentials.WORKSPACE_TOKEN_ENV, raising=False)
    monkeypatch.delenv(credentials.LEGACY_ACCESS_TOKEN_ENV, raising=False)
    monkeypatch.setenv(credentials.LEGACY_REFRESH_TOKEN_ENV, "refresh-secret")
    monkeypatch.setenv(credentials.CREDENTIALS_FILE_ENV, str(tmp_path / "credentials.json"))
    monkeypatch.setenv(credentials.DISABLE_KEYRING_ENV, "1")
    credentials._WORKSPACE_TOKEN_CACHE.clear()

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response({"access_token": "refreshed-access", "expires_in": 300})

    monkeypatch.setattr(credentials, "urlopen", fake_urlopen)
    assert credentials.resolve_token("hub.biosimulant.ai") == "refreshed-access"
    assert requests[0].get_header("Authorization") is None
    assert requests[0].full_url == f"{credentials.DEFAULT_HUB_API_BASE}/users/refresh"
    assert json.loads(requests[0].data) == {"token": "refresh-secret"}

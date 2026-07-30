from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from biosim import credentials


@pytest.fixture(autouse=True)
def _clear_workspace_token_cache() -> None:
    credentials._WORKSPACE_TOKEN_CACHE.clear()


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
    assert credentials.resolve_token("hub.biosimulant.com") == "operation-token"
    assert requests[0][0].get_header("Authorization") == "Bearer workspace-identity"
    assert requests[0][0].get_header("User-agent") == credentials.CLI_USER_AGENT
    assert requests[0][0].full_url == (
        f"{credentials.DEFAULT_HUB_API_BASE}/registry/v1/auth/exchange"
    )
    assert credentials.resolve_token("hub.biosimulant.com") == "operation-token"
    assert len(requests) == 1


def test_legacy_default_hub_access_token_remains_usable(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(credentials.TOKEN_ENV, raising=False)
    monkeypatch.delenv(credentials.WORKSPACE_TOKEN_ENV, raising=False)
    monkeypatch.setenv(credentials.LEGACY_ACCESS_TOKEN_ENV, "legacy-token")
    monkeypatch.setenv(credentials.CREDENTIALS_FILE_ENV, str(tmp_path / "credentials.json"))
    monkeypatch.setenv(credentials.DISABLE_KEYRING_ENV, "1")

    assert credentials.resolve_token("hub.biosimulant.com") == "legacy-token"
    assert credentials.credential_status("hub.biosimulant.com")["source"] == "legacy_environment"


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
    assert credentials.resolve_token("hub.biosimulant.com") == "refreshed-access"
    assert requests[0].get_header("Authorization") is None
    assert requests[0].get_header("User-agent") == credentials.CLI_USER_AGENT
    assert requests[0].full_url == f"{credentials.DEFAULT_HUB_API_BASE}/users/refresh"
    assert json.loads(requests[0].data) == {"token": "refresh-secret"}


def _http_error(status: int, payload: dict[str, object]) -> HTTPError:
    return HTTPError(
        "https://api.example/auth/exchange",
        status,
        "failure",
        hdrs=None,
        fp=io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


def _raw_http_error(status: int, payload: str) -> HTTPError:
    return HTTPError(
        "https://api.example/auth/exchange",
        status,
        "failure",
        hdrs=None,
        fp=io.BytesIO(payload.encode("utf-8")),
    )


@pytest.mark.parametrize(
    "payload",
    [
        "error code: 1010",
        json.dumps(
            {
                "detail": (
                    "The site owner has blocked access based on your browser's signature."
                )
            }
        ),
    ],
)
def test_workspace_exchange_gateway_client_block_is_not_reported_as_expired(
    monkeypatch,
    payload: str,
) -> None:
    monkeypatch.setattr(
        credentials,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            _raw_http_error(403, payload)
        ),
    )

    with pytest.raises(credentials.CredentialError) as exc_info:
        credentials._exchange_workspace_token(
            "https://hub.biosimulant.com",
            "workspace-secret",
        )

    assert exc_info.value.code == "workspace_registry_exchange_client_blocked"
    assert exc_info.value.exit_code == 7
    assert exc_info.value.details == {
        "failureCategory": "client_blocked",
        "httpStatus": 403,
        "attemptCount": 1,
        "backendMessage": (
            "error code: 1010"
            if payload == "error code: 1010"
            else "The site owner has blocked access based on your browser's signature."
        ),
    }


def test_workspace_exchange_unauthorized_is_structured_and_secret_safe(
    monkeypatch,
) -> None:
    workspace_secret = "workspace.identity.secret"
    leaked_backend_secret = "header-secret-value"
    monkeypatch.setattr(
        credentials,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            _http_error(
                401,
                {
                    "detail": (
                        f"Authorization: Bearer {leaked_backend_secret}; "
                        f"workspace_token={workspace_secret}; token=opaque-secret"
                    )
                },
            )
        ),
    )

    with pytest.raises(credentials.CredentialError) as exc_info:
        credentials._exchange_workspace_token(
            "https://hub.biosimulant.com",
            workspace_secret,
        )

    error = exc_info.value
    assert error.code == "workspace_registry_exchange_unauthorized"
    assert error.exit_code == 3
    assert error.details == {
        "failureCategory": "unauthorized",
        "httpStatus": 401,
        "attemptCount": 1,
        "backendMessage": (
            "Authorization=[redacted] [redacted]; workspace_token=[redacted]"
            "; token=[redacted]"
        ),
    }
    assert workspace_secret not in repr(error.details)
    assert leaked_backend_secret not in repr(error.details)
    assert "opaque-secret" not in repr(error.details)


def test_workspace_exchange_retries_stale_404_then_succeeds(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def fake_urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _http_error(404, {"detail": "not deployed yet"})
        return _Response({"accessToken": "operation-token", "expiresIn": 300})

    monkeypatch.setattr(credentials, "urlopen", fake_urlopen)
    monkeypatch.setattr(credentials.time, "sleep", sleeps.append)

    assert (
        credentials._exchange_workspace_token(
            "https://hub.biosimulant.com",
            "workspace-secret",
        )
        == "operation-token"
    )
    assert attempts == 3
    assert sleeps == [0.25, 0.75]


def test_workspace_exchange_network_failure_is_unavailable(monkeypatch) -> None:
    attempts = 0

    def fake_urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise URLError("DNS failed")

    monkeypatch.setattr(credentials, "urlopen", fake_urlopen)
    monkeypatch.setattr(credentials.time, "sleep", lambda _seconds: None)

    with pytest.raises(credentials.CredentialError) as exc_info:
        credentials._exchange_workspace_token(
            "https://hub.biosimulant.com",
            "workspace-secret",
        )

    assert attempts == 3
    assert exc_info.value.code == "workspace_registry_exchange_endpoint_unavailable"
    assert exc_info.value.details == {
        "failureCategory": "network",
        "httpStatus": None,
        "attemptCount": 3,
    }


def test_workspace_exchange_malformed_success_is_invalid_response(monkeypatch) -> None:
    monkeypatch.setattr(
        credentials,
        "urlopen",
        lambda *_args, **_kwargs: _Response({"expiresIn": 300}),
    )

    with pytest.raises(credentials.CredentialError) as exc_info:
        credentials._exchange_workspace_token(
            "https://hub.biosimulant.com",
            "workspace-secret",
        )

    assert exc_info.value.code == "workspace_registry_exchange_invalid_response"
    assert exc_info.value.details["attemptCount"] == 1

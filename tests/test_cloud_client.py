from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

import httpx
import pytest

from biosimulant import (
    AsyncClient,
    Client,
    RateLimitError,
    RunTimeout,
    verify_webhook_signature,
)


def test_sync_run_create_wait_and_result() -> None:
    requests: list[httpx.Request] = []
    statuses = iter(["queued", "completed"])

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"id": "run_1", "status": "queued"})
        if request.url.path.endswith("/results"):
            return httpx.Response(
                200,
                json={
                    "run_id": "run_1",
                    "outputs": {"population": 42},
                    "artifacts": [{"id": "artifact_1", "file_name": "result.csv"}],
                    "provenance": {"resolved_ref": "demo/growth@1.0.0"},
                },
            )
        return httpx.Response(200, json={"id": "run_1", "status": next(statuses)})

    with Client(api_key="bsk_test_secret", base_url="https://example.test/v1", transport=httpx.MockTransport(handler)) as client:
        result = client.run("demo/growth@1.0.0", inputs={"initial_cells": 10}, timeout=2)

    assert result.outputs == {"population": 42}
    assert result.artifacts[0].file_name == "result.csv"
    create = requests[0]
    assert create.headers["Idempotency-Key"]
    assert json.loads(create.content)["ref"] == "demo/growth@1.0.0"


def test_client_timeout_preserves_run_handle() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"id": "run_2", "status": "queued"})
        return httpx.Response(200, json={"id": "run_2", "status": "running"})

    with Client(api_key="bsk_test_secret", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RunTimeout) as raised:
            client.run("demo/growth@1.0.0", timeout=0)

    assert raised.value.run.id == "run_2"
    assert raised.value.run.status == "running"


def test_rate_limit_error_mapping() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded", "message": "Slow down"}},
        )

    with Client(api_key="bsk_test_secret", transport=httpx.MockTransport(handler), max_retries=0) as client:
        with pytest.raises(RateLimitError) as raised:
            client.capabilities()

    assert raised.value.code == "rate_limit_exceeded"


def test_events_cursor_and_artifact_download() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events"):
            assert request.url.params["after"] == "12"
            return httpx.Response(200, json={"items": [{"cursor": 13}], "next_cursor": 13})
        if "/artifacts/" not in request.url.path:
            return httpx.Response(200, json={"id": "run_3", "status": "completed"})
        return httpx.Response(200, content=b"artifact bytes")

    with Client(api_key="bsk_test_secret", transport=httpx.MockTransport(handler)) as client:
        run = client.runs.retrieve("run_3")
        assert run.events(after=12)["next_cursor"] == 13
        assert run.download_artifact("artifact_1") == b"artifact bytes"


def test_run_iterator_follows_pagination_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        if cursor is None:
            return httpx.Response(
                200,
                json={"items": [{"id": "run_1", "status": "completed"}], "next_cursor": "run_1"},
            )
        assert cursor == "run_1"
        return httpx.Response(
            200,
            json={"items": [{"id": "run_2", "status": "failed"}], "next_cursor": None},
        )

    with Client(api_key="bsk_test_secret", transport=httpx.MockTransport(handler)) as client:
        assert [run.id for run in client.runs.iter(page_size=1)] == ["run_1", "run_2"]


def test_async_client_parity() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    202,
                    json={
                        "id": "run_async",
                        "status": "queued",
                        "resolved_ref": "demo/growth@1.0.0",
                        "metadata": {"sample": "A"},
                    },
                )
            if request.url.path.endswith("/results"):
                return httpx.Response(200, json={"run_id": "run_async", "outputs": {"population": 42}})
            return httpx.Response(200, json={"id": "run_async", "status": "completed"})

        async with AsyncClient(api_key="bsk_test_secret", transport=httpx.MockTransport(handler)) as client:
            run = await client.runs.create(ref="demo/growth@1.0.0", metadata={"sample": "A"})
            assert run.ref == "demo/growth@1.0.0"
            assert run.metadata == {"sample": "A"}
            result = await run.wait(timeout=2)
            assert result.outputs == {"population": 42}

    asyncio.run(scenario())


def test_webhook_signature_verification() -> None:
    payload = b'{"type":"run.completed"}'
    timestamp = 1_700_000_000
    signature = hmac.new(
        b"whsec_test",
        str(timestamp).encode("ascii") + b"." + payload,
        hashlib.sha256,
    ).hexdigest()

    assert verify_webhook_signature(
        payload,
        f"t={timestamp},v1={signature}",
        "whsec_test",
        now=timestamp,
    )

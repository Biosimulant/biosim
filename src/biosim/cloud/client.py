"""Synchronous and asynchronous clients for managed Biosimulant execution."""

from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import httpx

from .errors import (
    ApiError,
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    RunFailed,
    RunTimeout,
    ValidationError,
)
from .types import RunResult, TERMINAL_RUN_STATUSES

DEFAULT_BASE_URL = "https://api.biosimulant.com/v1"


def _error_from_response(response: httpx.Response) -> ApiError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        detail = body.get("detail") if isinstance(body, dict) else None
        error = detail if isinstance(detail, dict) else {"message": detail or response.text or response.reason_phrase}
    kwargs = {
        "status_code": response.status_code,
        "code": error.get("code"),
        "param": error.get("param"),
        "details": error.get("details"),
        "request_id": error.get("request_id") or response.headers.get("X-Request-ID"),
    }
    message = str(error.get("message") or f"Biosimulant API returned HTTP {response.status_code}")
    error_type = error.get("type")
    if response.status_code == 401 or error_type == "authentication_error":
        return AuthenticationError(message, **kwargs)
    if response.status_code == 402 or error_type == "insufficient_credits_error":
        return InsufficientCreditsError(message, **kwargs)
    if response.status_code == 429 or error_type == "rate_limit_error":
        return RateLimitError(message, **kwargs)
    if response.status_code in {400, 409, 422} or error_type == "validation_error":
        return ValidationError(message, **kwargs)
    return ApiError(message, **kwargs)


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        raw = response.headers.get("Retry-After")
        try:
            if raw is not None:
                return min(10.0, max(0.0, float(raw)))
        except ValueError:
            pass
    return min(5.0, (0.25 * (2**attempt)) + random.uniform(0.0, 0.1))


class Run:
    def __init__(self, client: "Client", payload: dict[str, Any]) -> None:
        self._client = client
        self._payload = dict(payload)

    @property
    def id(self) -> str:
        return str(self._payload["id"])

    @property
    def status(self) -> str:
        return str(self._payload.get("status") or "queued")

    @property
    def ref(self) -> str | None:
        value = self._payload.get("resolved_ref") or self._payload.get("ref")
        return str(value) if value else None

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._payload.get("metadata") or {})

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._payload)

    def refresh(self) -> "Run":
        self._payload = self._client._request("GET", f"/runs/{self.id}")
        return self

    def cancel(self) -> "Run":
        self._payload = self._client._request("POST", f"/runs/{self.id}/cancel")
        return self

    def result(self) -> RunResult:
        return RunResult.from_dict(self._client._request("GET", f"/runs/{self.id}/results"))

    def events(self, *, after: int = 0, limit: int = 100) -> dict[str, Any]:
        return self._client._request(
            "GET",
            f"/runs/{self.id}/events",
            params={"after": after, "limit": limit},
        )

    def download_artifact(self, artifact_id: str) -> bytes:
        return self._client._request_bytes("GET", f"/runs/{self.id}/artifacts/{artifact_id}")

    def wait(self, timeout: float | None = None, *, poll_interval: float = 0.5) -> RunResult:
        started = time.monotonic()
        delay = max(0.05, poll_interval)
        while True:
            self.refresh()
            if self.status == "completed":
                return self.result()
            if self.status in TERMINAL_RUN_STATUSES:
                message = ((self._payload.get("error") or {}).get("message") or f"Run ended with status {self.status}")
                raise RunFailed(str(message), run=self)
            if timeout is not None and time.monotonic() - started >= timeout:
                raise RunTimeout(f"Run {self.id} is still {self.status}", run=self)
            time.sleep(delay)
            delay = min(5.0, delay * 1.5)


class RunsResource:
    def __init__(self, client: "Client") -> None:
        self._client = client

    def create(
        self,
        *,
        ref: str,
        inputs: dict[str, Any] | None = None,
        compute_profile: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Run:
        payload: dict[str, Any] = {"ref": ref, "inputs": inputs or {}, "metadata": metadata or {}}
        if compute_profile is not None:
            payload["compute_profile"] = compute_profile
        data = self._client._request(
            "POST",
            "/runs",
            json=payload,
            headers={"Idempotency-Key": idempotency_key or str(uuid4())},
        )
        return Run(self._client, data)

    def retrieve(self, run_id: str) -> Run:
        return Run(self._client, self._client._request("GET", f"/runs/{run_id}"))

    def list(self, *, limit: int = 50, cursor: str | None = None) -> list[Run]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        data = self._client._request("GET", "/runs", params=params)
        return [Run(self._client, item) for item in data.get("items") or []]

    def iter(self, *, page_size: int = 50) -> Iterator[Run]:
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": page_size}
            if cursor is not None:
                params["cursor"] = cursor
            data = self._client._request("GET", "/runs", params=params)
            for item in data.get("items") or []:
                yield Run(self._client, item)
            cursor = data.get("next_cursor")
            if not cursor:
                break


class Client:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("BIOSIMULANT_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError("Set BIOSIMULANT_API_KEY or pass api_key to Client")
        self.base_url = (base_url or os.getenv("BIOSIMULANT_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max(0, int(max_retries))
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "biosimulant-python"},
        )
        self.runs = RunsResource(self)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise ApiError(f"Biosimulant API request failed: {exc}") from exc
                time.sleep(_retry_delay(None, attempt))
                continue
            last_response = response
            if response.status_code < 400:
                if not response.content:
                    return {}
                value = response.json()
                return value if isinstance(value, dict) else {"items": value}
            if response.status_code not in {408, 425, 429, 500, 502, 503, 504} or attempt >= self.max_retries:
                raise _error_from_response(response)
            time.sleep(_retry_delay(response, attempt))
        raise _error_from_response(last_response) if last_response is not None else ApiError("Request failed")

    def _request_bytes(self, method: str, path: str, **kwargs: Any) -> bytes:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise ApiError(f"Biosimulant API request failed: {exc}") from exc
                time.sleep(_retry_delay(None, attempt))
                continue
            if response.status_code < 400:
                return response.content
            if response.status_code not in {408, 425, 429, 500, 502, 503, 504} or attempt >= self.max_retries:
                raise _error_from_response(response)
            time.sleep(_retry_delay(response, attempt))
        raise ApiError("Request failed")

    def run(
        self,
        ref: str,
        *,
        inputs: dict[str, Any] | None = None,
        compute_profile: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> RunResult:
        run = self.runs.create(
            ref=ref,
            inputs=inputs,
            compute_profile=compute_profile,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return run.wait(timeout=timeout)

    def capabilities(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._request("GET", "/capabilities", params={"limit": limit}).get("items") or [])

    def compute_profiles(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/compute-profiles").get("items") or [])

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class AsyncRun:
    def __init__(self, client: "AsyncClient", payload: dict[str, Any]) -> None:
        self._client = client
        self._payload = dict(payload)

    @property
    def id(self) -> str:
        return str(self._payload["id"])

    @property
    def status(self) -> str:
        return str(self._payload.get("status") or "queued")

    @property
    def ref(self) -> str | None:
        value = self._payload.get("resolved_ref") or self._payload.get("ref")
        return str(value) if value else None

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._payload.get("metadata") or {})

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._payload)

    async def refresh(self) -> "AsyncRun":
        self._payload = await self._client._request("GET", f"/runs/{self.id}")
        return self

    async def cancel(self) -> "AsyncRun":
        self._payload = await self._client._request("POST", f"/runs/{self.id}/cancel")
        return self

    async def result(self) -> RunResult:
        return RunResult.from_dict(await self._client._request("GET", f"/runs/{self.id}/results"))

    async def events(self, *, after: int = 0, limit: int = 100) -> dict[str, Any]:
        return await self._client._request(
            "GET",
            f"/runs/{self.id}/events",
            params={"after": after, "limit": limit},
        )

    async def download_artifact(self, artifact_id: str) -> bytes:
        return await self._client._request_bytes(
            "GET",
            f"/runs/{self.id}/artifacts/{artifact_id}",
        )

    async def wait(self, timeout: float | None = None, *, poll_interval: float = 0.5) -> RunResult:
        loop = asyncio.get_running_loop()
        started = loop.time()
        delay = max(0.05, poll_interval)
        while True:
            await self.refresh()
            if self.status == "completed":
                return await self.result()
            if self.status in TERMINAL_RUN_STATUSES:
                message = ((self._payload.get("error") or {}).get("message") or f"Run ended with status {self.status}")
                raise RunFailed(str(message), run=self)
            if timeout is not None and loop.time() - started >= timeout:
                raise RunTimeout(f"Run {self.id} is still {self.status}", run=self)
            await asyncio.sleep(delay)
            delay = min(5.0, delay * 1.5)


class AsyncRunsResource:
    def __init__(self, client: "AsyncClient") -> None:
        self._client = client

    async def create(
        self,
        *,
        ref: str,
        inputs: dict[str, Any] | None = None,
        compute_profile: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> AsyncRun:
        payload: dict[str, Any] = {"ref": ref, "inputs": inputs or {}, "metadata": metadata or {}}
        if compute_profile is not None:
            payload["compute_profile"] = compute_profile
        data = await self._client._request(
            "POST",
            "/runs",
            json=payload,
            headers={"Idempotency-Key": idempotency_key or str(uuid4())},
        )
        return AsyncRun(self._client, data)

    async def retrieve(self, run_id: str) -> AsyncRun:
        return AsyncRun(self._client, await self._client._request("GET", f"/runs/{run_id}"))

    async def list(self, *, limit: int = 50, cursor: str | None = None) -> list[AsyncRun]:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        data = await self._client._request("GET", "/runs", params=params)
        return [AsyncRun(self._client, item) for item in data.get("items") or []]

    async def iter(self, *, page_size: int = 50) -> AsyncIterator[AsyncRun]:
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": page_size}
            if cursor is not None:
                params["cursor"] = cursor
            data = await self._client._request("GET", "/runs", params=params)
            for item in data.get("items") or []:
                yield AsyncRun(self._client, item)
            cursor = data.get("next_cursor")
            if not cursor:
                break


class AsyncClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("BIOSIMULANT_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError("Set BIOSIMULANT_API_KEY or pass api_key to AsyncClient")
        self.base_url = (base_url or os.getenv("BIOSIMULANT_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max(0, int(max_retries))
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "biosimulant-python"},
        )
        self.runs = AsyncRunsResource(self)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise ApiError(f"Biosimulant API request failed: {exc}") from exc
                await asyncio.sleep(_retry_delay(None, attempt))
                continue
            last_response = response
            if response.status_code < 400:
                if not response.content:
                    return {}
                value = response.json()
                return value if isinstance(value, dict) else {"items": value}
            if response.status_code not in {408, 425, 429, 500, 502, 503, 504} or attempt >= self.max_retries:
                raise _error_from_response(response)
            await asyncio.sleep(_retry_delay(response, attempt))
        raise _error_from_response(last_response) if last_response is not None else ApiError("Request failed")

    async def _request_bytes(self, method: str, path: str, **kwargs: Any) -> bytes:
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise ApiError(f"Biosimulant API request failed: {exc}") from exc
                await asyncio.sleep(_retry_delay(None, attempt))
                continue
            if response.status_code < 400:
                return response.content
            if response.status_code not in {408, 425, 429, 500, 502, 503, 504} or attempt >= self.max_retries:
                raise _error_from_response(response)
            await asyncio.sleep(_retry_delay(response, attempt))
        raise ApiError("Request failed")

    async def run(
        self,
        ref: str,
        *,
        inputs: dict[str, Any] | None = None,
        compute_profile: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
        idempotency_key: str | None = None,
    ) -> RunResult:
        run = await self.runs.create(
            ref=ref,
            inputs=inputs,
            compute_profile=compute_profile,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return await run.wait(timeout=timeout)

    async def capabilities(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list((await self._request("GET", "/capabilities", params={"limit": limit})).get("items") or [])

    async def compute_profiles(self) -> list[dict[str, Any]]:
        return list((await self._request("GET", "/compute-profiles")).get("items") or [])

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

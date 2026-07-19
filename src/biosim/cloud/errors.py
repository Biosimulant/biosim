"""Typed exceptions raised by the managed Biosimulant client."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        param: str | None = None,
        details: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.param = param
        self.details = details
        self.request_id = request_id


class AuthenticationError(ApiError):
    pass


class ValidationError(ApiError):
    pass


class RateLimitError(ApiError):
    pass


class InsufficientCreditsError(ApiError):
    pass


class RunFailed(ApiError):
    def __init__(self, message: str, *, run: Any) -> None:
        super().__init__(message, code="run_failed")
        self.run = run


class RunTimeout(ApiError):
    def __init__(self, message: str, *, run: Any) -> None:
        super().__init__(message, code="client_timeout")
        self.run = run

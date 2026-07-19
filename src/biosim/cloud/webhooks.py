"""Verification helpers for Biosimulant webhook requests."""

from __future__ import annotations

import hashlib
import hmac
import time

from .errors import ValidationError


def verify_webhook_signature(
    payload: bytes | str,
    signature: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    values: dict[str, list[str]] = {}
    for item in signature.split(","):
        key, separator, value = item.partition("=")
        if separator:
            values.setdefault(key.strip(), []).append(value.strip())
    try:
        timestamp = int(values["t"][0])
    except (KeyError, IndexError, ValueError) as exc:
        raise ValidationError("Webhook signature is malformed", code="invalid_webhook_signature") from exc
    current = int(time.time()) if now is None else int(now)
    if abs(current - timestamp) > max(0, int(tolerance_seconds)):
        raise ValidationError("Webhook signature timestamp is outside the tolerance", code="expired_webhook_signature")
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("ascii") + raw,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in values.get("v1", [])):
        raise ValidationError("Webhook signature does not match", code="invalid_webhook_signature")
    return True

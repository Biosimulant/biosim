"""Managed Developer API patterns (requires BIOSIMULANT_API_KEY)."""

from __future__ import annotations

import asyncio
import os

from biosimulant import AsyncClient, Client, RunTimeout, verify_webhook_signature

LAB_REF = "demi/microbiology-hello-world-growth@1.0.0"


def blocking() -> dict:
    with Client() as client:
        return client.run(LAB_REF, inputs={"initial_cells": 10}, timeout=300).outputs


def background_and_cancel() -> str:
    with Client() as client:
        run = client.runs.create(ref=LAB_REF, metadata={"sample": "A"})
        run.cancel()
        return run.id


def timeout_recovery() -> str:
    with Client() as client:
        run = client.runs.create(ref=LAB_REF)
        try:
            run.wait(timeout=10)
        except RunTimeout as exc:
            return exc.run.id  # the durable server execution is still active
        return run.id


async def parallel() -> list[dict]:
    async with AsyncClient() as client:
        results = await asyncio.gather(
            *(client.run(LAB_REF, inputs={"initial_cells": value}) for value in (10, 20, 40))
        )
        return [result.outputs for result in results]


def verify_webhook(payload: bytes, signature: str) -> bool:
    return verify_webhook_signature(payload, signature, os.environ["BIOSIMULANT_WEBHOOK_SECRET"])


if __name__ == "__main__":
    print(blocking())

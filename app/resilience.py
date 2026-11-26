import asyncio
import logging
import os
import random
import time

from google.genai.errors import APIError

logger = logging.getLogger(__name__)

RETRY_CODES = {429, 500, 503}
ATTEMPTS_PER_MODEL = 3


def model_chain(primary: str) -> list[str]:
    """Primary model first, then the optional fallback from GEMINI_FALLBACK_MODEL."""
    fallback = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()
    return [primary] + ([fallback] if fallback and fallback != primary else [])


def backoff(attempt: int) -> float:
    return min(8.0, 1.5 * 2 ** attempt) + random.random()  # jitter avoids retry stampedes


def _classify(exc: APIError) -> str:
    """'retry' = try this model again, 'next' = give up on this model, 'raise' = real error."""
    if exc.code == 504:  # deadline exceeded: retrying the same slow model rarely helps
        return "next"
    if exc.code not in RETRY_CODES:
        return "raise"
    if "PerDay" in str(exc):  # daily quota won't recover in seconds
        return "next"
    return "retry"


async def acall(fn, models: list[str], sleep=asyncio.sleep):
    """fn(model) is an async callable. Retry transient errors, then fall back to the next model."""
    last = None
    for model in models:
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                return await fn(model)
            except APIError as exc:
                action = _classify(exc)
                if action == "raise":
                    raise
                last = exc
                logger.warning("model=%s attempt=%d code=%s action=%s", model, attempt + 1, exc.code, action)
                if action == "next":
                    break
                if attempt < ATTEMPTS_PER_MODEL - 1:
                    await sleep(backoff(attempt))
    raise last


def call(fn, models: list[str], sleep=time.sleep):
    """Same as acall, for sync code."""
    last = None
    for model in models:
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                return fn(model)
            except APIError as exc:
                action = _classify(exc)
                if action == "raise":
                    raise
                last = exc
                logger.warning("model=%s attempt=%d code=%s action=%s", model, attempt + 1, exc.code, action)
                if action == "next":
                    break
                if attempt < ATTEMPTS_PER_MODEL - 1:
                    sleep(backoff(attempt))
    raise last
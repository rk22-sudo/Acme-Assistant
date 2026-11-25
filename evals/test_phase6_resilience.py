import anyio
import pytest
from google.genai.errors import APIError

from app import resilience


def err(code, msg="x"):
    return APIError(code, {"error": {"code": code, "message": msg, "status": "X"}})


async def no_sleep(_):
    return None


def run(fn, models):
    return anyio.run(lambda: resilience.acall(fn, models, sleep=no_sleep))


def test_retries_then_succeeds():
    calls = []

    async def fn(model):
        calls.append(model)
        if len(calls) < 3:
            raise err(503)
        return "ok"

    assert run(fn, ["a"]) == "ok"
    assert calls == ["a", "a", "a"]


def test_non_retryable_error_raises_immediately():
    calls = []

    async def fn(model):
        calls.append(model)
        raise err(400)

    with pytest.raises(APIError):
        run(fn, ["a", "b"])
    assert calls == ["a"]


def test_falls_back_after_exhausting_retries():
    calls = []

    async def fn(model):
        calls.append(model)
        if model == "a":
            raise err(503)
        return "from-b"

    assert run(fn, ["a", "b"]) == "from-b"
    assert calls == ["a", "a", "a", "b"]


def test_daily_quota_skips_retries_and_uses_fallback():
    calls = []

    async def fn(model):
        calls.append(model)
        if model == "a":
            raise err(429, "quota exceeded PerDay")
        return "from-b"

    assert run(fn, ["a", "b"]) == "from-b"
    assert calls == ["a", "b"]


def test_all_models_failing_raises_last_error():
    async def fn(model):
        raise err(503)

    with pytest.raises(APIError):
        run(fn, ["a", "b"])


def test_model_chain_dedupes_and_skips_empty(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")
    assert resilience.model_chain("a") == ["a"]
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "a")
    assert resilience.model_chain("a") == ["a"]
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "b")
    assert resilience.model_chain("a") == ["a", "b"]
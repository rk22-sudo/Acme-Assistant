import contextvars
import json
import logging
import math
import os
import time
import uuid
from collections import Counter, deque
from datetime import datetime, timezone

_current: contextvars.ContextVar = contextvars.ContextVar("request_obs", default=None)
_LATENCIES: deque = deque(maxlen=500)
_EVENTS: deque = deque(maxlen=200)
_COUNTS: Counter = Counter()
_STATUS: Counter = Counter()
_TOOLS: Counter = Counter()
_STARTED = time.time()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        row.update(getattr(record, "fields", {}))
        if record.exc_info:
            row["exc"] = record.exc_info[0].__name__  # class only; messages can hold user text
        return json.dumps(row, default=str)


def setup_logging() -> None:
    """JSON logs for everything under the 'app' logger. Safe to call twice."""
    logger = logging.getLogger("app")
    if any(getattr(h, "_obs", False) for h in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._obs = True
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


# ---- per-request context ----
def start_request() -> dict:
    ctx = {"request_id": uuid.uuid4().hex[:12], "t0": time.perf_counter(), "model_calls": 0,
           "prompt_tokens": 0, "output_tokens": 0, "tools": []}
    _current.set(ctx)
    return ctx


def note(**fields) -> None:
    """Attach fields to the current request. No-op outside a request (e.g. direct agent.run in tests)."""
    ctx = _current.get()
    if ctx is not None:
        ctx.update(fields)


def note_tools(names: list[str]) -> None:
    ctx = _current.get()
    if ctx is not None:
        ctx["tools"].extend(names)


def add_usage(resp, fallback_model: str) -> None:
    """Count one Gemini call and its tokens."""
    ctx = _current.get()
    if ctx is None:
        return
    usage = getattr(resp, "usage_metadata", None)
    ctx["model_calls"] += 1
    ctx["prompt_tokens"] += getattr(usage, "prompt_token_count", None) or 0
    ctx["output_tokens"] += getattr(usage, "candidates_token_count", None) or 0
    ctx["model"] = getattr(resp, "model_version", None) or fallback_model


def finish_request(ctx: dict, method: str, path: str, status: int, error: str | None = None) -> dict:
    event = {
        "request_id": ctx["request_id"], "method": method, "path": path, "status": status,
        "latency_ms": round((time.perf_counter() - ctx["t0"]) * 1000),
        "employee_id": ctx.get("employee_id"), "cache": ctx.get("cache"),
        "blocked": bool(ctx.get("blocked")), "model": ctx.get("model"),
        "model_calls": ctx["model_calls"], "prompt_tokens": ctx["prompt_tokens"],
        "output_tokens": ctx["output_tokens"], "tools": list(ctx["tools"]), "error": error,
    }
    _COUNTS["requests"] += 1
    _COUNTS["errors"] += status >= 500
    _COUNTS["cache_hits"] += event["cache"] == "hit"
    _COUNTS["cache_misses"] += event["cache"] == "miss"
    _COUNTS["blocked"] += event["blocked"]
    _COUNTS["model_calls"] += event["model_calls"]
    _COUNTS["prompt_tokens"] += event["prompt_tokens"]
    _COUNTS["output_tokens"] += event["output_tokens"]
    _STATUS[str(status)] += 1
    _TOOLS.update(event["tools"])
    _LATENCIES.append(event["latency_ms"])
    _EVENTS.append(event)
    _current.set(None)
    logging.getLogger("app.requests").info("request", extra={"fields": event})
    return event


# ---- reading metrics ----
def recent(n: int = 10) -> list[dict]:
    return list(_EVENTS)[-n:]  # oldest first


def summary() -> dict:
    lat = sorted(_LATENCIES)

    def pct(p: int):
        return lat[min(len(lat) - 1, math.ceil(p / 100 * len(lat)) - 1)] if lat else None

    lookups = _COUNTS["cache_hits"] + _COUNTS["cache_misses"]
    return {
        "uptime_s": round(time.time() - _STARTED),
        "requests": _COUNTS["requests"],
        "by_status": dict(_STATUS),
        "errors_5xx": _COUNTS["errors"],
        "blocked_injection": _COUNTS["blocked"],
        "cache": {"hits": _COUNTS["cache_hits"], "misses": _COUNTS["cache_misses"],
                  "hit_rate": round(_COUNTS["cache_hits"] / lookups, 3) if lookups else None},
        "model_calls": _COUNTS["model_calls"],
        "tokens": {"prompt": _COUNTS["prompt_tokens"], "output": _COUNTS["output_tokens"]},
        "tools": dict(_TOOLS),
        "latency_ms": {"p50": pct(50), "p95": pct(95), "n": len(lat)},
        "recent": recent(10),
    }


def reset() -> None:
    """For tests."""
    for c in (_COUNTS, _STATUS, _TOOLS, _LATENCIES, _EVENTS):
        c.clear()
    _current.set(None)
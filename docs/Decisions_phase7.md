# Phase 7 decisions
- Structured JSON logs (app/observability.py) with a per-request record: request id, latency, cache hit/miss, model, token counts, tool names, employee id. Message text is never logged (Phase 5 privacy rule).
- Per-request state lives in a contextvar, filled by the middleware, endpoint and agent, so no function signatures changed.
- In-memory metrics, exposed at GET /metrics for hr_admin only. Resets on restart.
- CI runs only offline tests: the search index is gitignored and live tests need the API key and the 1000/day embedding quota. Live evals are a local step before each tag.
- A hygiene test fails the build if .env or a Google API key-like string is committed.
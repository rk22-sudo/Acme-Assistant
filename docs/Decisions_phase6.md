# Phase 6 decisions

- Retry transient Gemini 429, 500, and 503 errors up to three times per model with backoff. A daily `PerDay` quota error skips retries for that model and moves directly to the configured fallback model.
- Route requests with a local heuristic based on the last user message and count of user turns. The router makes no model or network calls. It uses `GEMINI_MODEL` for ordinary requests and `GEMINI_STRONG_MODEL` for long or complex requests when configured.
- Cache only single-turn handbook answers with sources and no pending actions. Personal or tool-backed answers must never be served to another user (RBAC).
- Try exact normalized question matches first. Semantic matching is optional and should be enabled only after the probe data supports a measured threshold.
- Keep the response cache in process memory. It stores the redacted reply and sources, not tool call details or action tokens.
- Semantic cache measured and rejected: paraphrase similarity 0.803-0.902 overlaps different-question/personal-vs-policy similarity up to 0.871 (gemini-embedding-001, 768 dims, 16 pairs). CACHE_THRESHOLD stays unset; only exact-match caching is active.

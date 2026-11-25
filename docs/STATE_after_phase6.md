# STATE after Phase 6 (resilience, model routing, and response cache)

Env: Windows PowerShell, Python 3.12.7 in `.venv` (activate: `.\.venv\Scripts\Activate.ps1`)
Run: `uvicorn app.main:app --reload` | Offline tests: `.\.venv\Scripts\python.exe -m pytest evals -m "not live" -q` | Live tests: `.\.venv\Scripts\python.exe -m pytest evals -m live -q` (Gemini; network and `GEMINI_API_KEY` required)

Files added or changed in Phase 6:
- `app/resilience.py`: synchronous and asynchronous Gemini retry/fallback helpers.
- `app/router.py`: offline heuristic selection of fast or strong model.
- `app/cache.py`: expiring bounded response cache and handbook-only eligibility check.
- `app/llm.py`, `app/agent.py`: route model calls through retry/fallback and the router.
- `app/main.py`: exact-match cache lookup and storage for eligible redacted handbook responses.
- `scripts/cache_probe.py`: embedding similarity probe for paraphrases, nearby distinct questions, and personal-versus-policy questions (not run here).
- `evals/test_phase6_resilience.py`, `evals/test_phase6_router.py`, `evals/test_phase6_cache.py`, `evals/test_phase6_cache_wiring.py`, `evals/test_phase6_live.py`, `evals/conftest.py`: resilience, router, cache, endpoint wiring, and live behavior coverage.
- `docs/Decisions_phase6.md`, `docs/STATE_after_phase6.md`: phase decisions and state.

Environment variables:
- `GEMINI_MODEL`: fast/default model; defaults to `gemini-3.5-flash-lite`.
- `GEMINI_STRONG_MODEL`: optional model for long or complex requests.
- `GEMINI_FALLBACK_MODEL`: optional fallback model after retries.
- `CACHE_THRESHOLD`: leave unset. Semantic matching is disabled by measurement (see known gaps).

Known gaps:
- Cache is in-memory and per-process; entries are not shared or persisted.
- Semantic cache matching is implemented but remains disabled until a measured threshold is selected.
- Model routing is a heuristic and may not classify every request well.
- Semantic cache is rejected, not pending: measured paraphrase similarity (0.803-0.902) overlaps wrong-pair similarity (up to 0.871) with gemini-embedding-001 at 768 dims, 16 pairs. The matching code exists but stays off (CACHE_THRESHOLD unset). Revisit only with a different embedding model or a re-ranking step.
- Each fallback or retry multiplies Gemini requests per chat (up to 3 attempts x 2 models per round, 4 rounds), so a bad outage can burn the free-tier quota quickly.
- Only exact-match caching is live, and it only covers single-turn handbook answers.

Verified (user's terminal, 2026-11-25): 95 offline passed, 32 deselected; evals/test_phase6_live.py 2 passed; cache_probe: paraphrases min 0.803 vs wrong-pair max 0.871, so semantic cache left off.
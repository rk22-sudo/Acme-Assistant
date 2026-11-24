# STATE after Phase 5 (guardrails and write confirmation)
Env: Windows PowerShell, Python 3.12.7 in `.venv` (activate: `.\.venv\Scripts\Activate.ps1`)
Run: `uvicorn app.main:app --reload` | Offline tests: `pytest evals -m "not live" -v` | Live tests: `pytest evals -m live -v` (Gemini; network and `GEMINI_API_KEY` required)

Files added or changed in Phase 5:
- `app/guardrails.py`: heuristic regex injection detection, refusal text, and selective PII redaction (EMAIL, SSN, CARD, PHONE).
- `app/main.py`: checks injection across every client-supplied message after authentication; redacts all PII kinds on input and SSN/CARD in replies; trims HTTP tool-call data; returns signed confirmation actions. Adds `POST /chat/confirm`.
- `app/agent.py`: skips injection-flagged handbook chunks, queues write tools without executing them, returns `pending_actions`, and adds `execute_tool` for confirmed writes.
- `app/auth.py`: creates and verifies five-minute action tokens using HS256 and a separate issuer from login tokens.
- `app/prompts.py`: instructs the model to explain queued writes and wait for confirmation.
- `scripts/scan_corpus.py`: offline scan of indexed handbook chunks for injection patterns and PII-like text.
- `evals/test_phase5_guardrails.py`, `evals/test_phase5_wiring.py`, `evals/test_phase5_confirm.py`, `evals/test_phase5_live.py`: guardrail, API wiring, confirmation-token, and live behavior coverage. The live eval file is marked `live` and was not verified here.
- `evals/test_phase3_agent.py`, `evals/test_phase4_agent_live.py`: write-action evals updated for queue-and-confirm behavior.
- `docs/Decisions_phase5.md`, `docs/STATE_after_phase5.md`: phase decisions and state.

Guardrails:
- Prompt injection detection is heuristic regex matching. Check all client-supplied messages, including assistant history, before calling the agent. On a match, return the fixed refusal and log pattern names plus employee ID without logging message text.
- Run the same detector over handbook chunks before they reach the model. Skip matching chunks and log only the chunk ID and pattern names.
- Redact all PII kinds (EMAIL, SSN, CARD, PHONE) from input messages. On replies, redact SSN and CARD only, since handbook contact emails are public and useful to retain.
- Corpus scan result: 0/992 injection-flagged chunks and 44 chunks with PII-like text. These heuristic counts do not establish that every chunk is safe or free of sensitive data.

Write confirmation:
- `request_leave`, `approve_leave`, `create_ticket`, and `send_slack_message` are queued by the agent and are not executed in its tool loop. `app.agent.run` returns `pending_actions`; queued args do not include `employee_id`.
- `/chat` returns an action token with each pending action. The token uses HS256, expires in five minutes, and has a separate issuer from login tokens. `/chat/confirm` requires bearer authentication and rejects the action unless its `sub` matches the authenticated caller.
- `POST /chat/confirm` verifies and executes a confirmed write, returning `{"result": ...}`. Unknown/non-write tool names are rejected.
- `POST /chat` retains the existing chat endpoint behavior and now returns trimmed tool calls (`name`, `ok`) plus `pending_actions`. Existing `POST /auth/token` remains the development mock-login endpoint.

Known gaps:
- Regex injection detection is bypassable and is only one guardrail layer; it is not a complete prompt-injection defense.
- No rate limiting.
- Mock login (`MOCK_LOGIN=1`) is for development only and must never ship enabled.
- An MCP subprocess is started per agent request and per confirmed write.
- No 503/429 retry yet (Phase 6).

Verified: <PASTE MY TERMINAL OUTPUT HERE>

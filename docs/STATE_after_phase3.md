# STATE after Phase 3 (tag v3-agent)
Env: Windows PowerShell, Python 3.12.7 in .venv (activate: .\.venv\Scripts\Activate.ps1)
Run: uvicorn app.main:app --reload | Offline tests: pytest evals -m "not live" -v (no network) | Live tests: pytest evals -m live -v (Gemini; rerun failures with --lf)
LLM: Gemini via google-genai, GEMINI_MODEL=gemini-3.5-flash-lite. Embeddings: gemini-embedding-001, 768 dims. Key in GEMINI_API_KEY (.env, gitignored).
MCP SDK: mcp>=2,<3 (installed 2.3.0). v2 renamed FastMCP to MCPServer (from mcp.server.mcpserver import MCPServer), model fields are snake_case (input_schema, is_error). Client side uses the lowlevel ClientSession + mcp.client.stdio.stdio_client; the high-level Client class is not used.
Debug tip: when the tool server crashes on startup the agent only shows "MCPError: Connection closed". The real error is in the captured stderr.

Files added or changed in Phase 3:
- app/tools.py: plain functions get_leave_balance, request_leave, create_ticket, list_tickets, send_slack_message. Return {"error": ...} dicts instead of raising. State is written to data/state/*.jsonl (gitignored); folder override via env var HANDBOOK_STATE_DIR.
- app/mcp_server.py: MCPServer("handbook-tools") exposing those 5 tools over stdio (never print() in it: stdout is the protocol channel).
- app/agent.py: run(messages, employee_id, state_dir=None) -> {reply, sources, tool_calls}. Starts the MCP server as a subprocess, converts MCP tools to Gemini function declarations, manual function-calling loop (automatic calling disabled), MAX_ROUNDS=4. employee_id is hidden from the model's tool schemas and injected by the agent. search_handbook is an extra tool wrapping app.retrieval.search; source numbers are global across searches. _leaf() unwraps ExceptionGroups so main.py can map provider errors.
- app/prompts.py: AGENT_RULES appended.
- app/main.py: /chat now calls the agent (async) and returns {reply, sources, tool_calls}. DEMO_EMPLOYEE_ID (env, default E001) stands in for a logged-in user. MCPError -> 503. rag.answer is kept (Phase 2 evals call it directly).
- data/synthetic/employees.json: 3 fake employees. This is a fictional HR system, not GitLab's real PTO policy.
- scripts/mcp_smoke.py (lists tools over stdio), scripts/agent_cli.py (python -m scripts.agent_cli "question").
- pytest.ini: marker "live". All Gemini-calling test files are marked live.
- evals: test_phase3_tools.py (9, offline), test_phase3_agent_unit.py (6, offline), test_phase3_agent.py (7, live), test_phase3_api.py (2, live). Offline total 15.

Verified (user's terminal, 2026-11-23): all 7 live agent evals and 2 live API evals passed (one earlier run hit a Gemini 503 on one test and passed on rerun); manual POST to /chat under uvicorn returned a correct get_leave_balance answer (14 annual days remaining for E001).

Known gaps:
- Identity is a hardcoded demo user. The model cannot choose employee_id, but there is no auth, no roles, no manager-approval rules (Phase 4).
- /chat returns raw tool_calls including tool results. Fine with synthetic data; redact in Phase 5 (guardrails/PII).
- No confirmation step before write actions (leave request, ticket, Slack post). Prompt-only rule today.
- No 503/429 retry or fallback on generation (llm.py and agent.py make one attempt). Phase 6.
- A new MCP subprocess is started per /chat request (extra latency). Consider a long-lived session in Phase 6/7.
- Tool results with structured_content are null (functions return a plain dict); the agent parses the JSON text content instead.
- No similarity cutoff for handbook search (unchanged from Phase 2). Only 5 handbook folders indexed.
- Editor Pyrefly warnings vanish after selecting the .venv interpreter. README.md is untracked on purpose.
Workflow note: Antigravity/Codex sandbox has NO network. Live calls and live evals run in my own terminal.

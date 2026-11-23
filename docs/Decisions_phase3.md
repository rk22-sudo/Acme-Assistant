* MCP SDK v2 (2.3.0), pinned mcp>=2,<3. FastMCP was renamed MCPServer; used the lowlevel ClientSession + stdio_client for the client.
* Tools are plain Python functions (app/tools.py) wrapped by a thin MCP server, so they are unit-testable offline.
* The agent hides employee_id from the model and injects it; real identity comes in Phase 4.
* Manual Gemini function-calling loop with MAX_ROUNDS=4 to control free-tier request usage.
* search_handbook is a tool inside the agent; rag.answer stays for the Phase 2 evals.
* Synthetic HR data is fictional and not GitLab's PTO policy.
* HANDBOOK_STATE_DIR env var isolates test state because the MCP server is a separate process.
* Tools return {"error": ...} dicts so the model can explain failures instead of the call crashing.
* pytest marker "live" separates Gemini-calling tests from offline tests (used again for CI in Phase 7).

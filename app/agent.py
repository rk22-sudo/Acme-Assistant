import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

import anyio
from google.genai import types
from mcp import ClientSession, MCPError, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.llm import MODEL, _get_client
from app.guardrails import detect_injection
from app.prompts import AGENT_RULES, SYSTEM_PROMPT
from app.retrieval import search

ROOT = Path(__file__).resolve().parent.parent
MAX_ROUNDS = 4  # each round is one Gemini request; the free tier is tight
TOP_K = 5
IDENTITY_ARG = "employee_id"  # injected by us, never chosen by the model
WRITE_TOOLS = {"request_leave", "approve_leave", "create_ticket", "send_slack_message"}
logger = logging.getLogger(__name__)

SEARCH_TOOL = types.FunctionDeclaration(
    name="search_handbook",
    description="Search GitLab's public handbook. Use for any question about policy, process or how things work.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"query": types.Schema(type="STRING", description="What to look up, in plain words")},
        required=["query"],
    ),
)


def _schema(prop: dict) -> types.Schema:
    kind = prop.get("type")
    if kind not in ("string", "integer", "number", "boolean"):
        raise ValueError(f"Unsupported tool argument type: {prop}")
    return types.Schema(type=kind.upper(), description=prop.get("description"))


def to_declaration(tool) -> types.FunctionDeclaration:
    """MCP tool -> Gemini function declaration, with the identity argument hidden."""
    schema = tool.input_schema
    props = {k: _schema(v) for k, v in schema.get("properties", {}).items() if k != IDENTITY_ARG}
    required = [r for r in schema.get("required", []) if r != IDENTITY_ARG]
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=types.Schema(type="OBJECT", properties=props, required=required or None) if props else None,
    )


def build_args(name: str, args: dict, takes_identity: set[str], employee_id: str) -> dict:
    """Drop anything the model supplied for identity, then inject the real one."""
    clean = {k: v for k, v in args.items() if k != IDENTITY_ARG}
    if name in takes_identity:
        clean[IDENTITY_ARG] = employee_id
    return clean


def _parse(result) -> dict:
    text = "".join(b.text for b in result.content if getattr(b, "type", None) == "text")
    if result.is_error:
        return {"error": text}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


async def _search_handbook(query: str, sources: list[dict]) -> dict:
    hits = await anyio.to_thread.run_sync(search, query, TOP_K)  # embedding call blocks, keep it off the loop
    out = []
    for h in hits:
        patterns = detect_injection(h["text"])
        if patterns:
            logger.warning(
                "Skipped poisoned handbook chunk id=%s; patterns=%s",
                h["id"],
                patterns,
            )
            continue
        n = next((i for i, s in enumerate(sources, 1) if s["id"] == h["id"]), None)
        if n is None:
            sources.append(h)
            n = len(sources)
        out.append(f"[{n}] {h['title']} > {h['heading']}\n{h['text']}")
    return {"sources": "\n\n".join(out)}


def _leaf(exc: BaseException) -> BaseException:
    """anyio/MCP task groups wrap errors in ExceptionGroups; dig out the real one."""
    while isinstance(exc, BaseExceptionGroup):
        exc = exc.exceptions[0]
    return exc


async def run(messages: list[dict], employee_id: str, state_dir: str | None = None) -> dict:
    try:
        return await _run(messages, employee_id, state_dir)
    except BaseExceptionGroup as group:
        raise _leaf(group) from group


async def execute_tool(name: str, args: dict, employee_id: str, state_dir: str | None = None) -> dict:
    """Execute a confirmed write tool as the authenticated employee."""
    if name not in WRITE_TOOLS:
        raise ValueError(f"Tool is not a confirmable write: {name}")
    env = {"HANDBOOK_STATE_DIR": state_dir} if state_dir else None
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(ROOT), env=env
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                mcp_tools = (await session.list_tools()).tools
                takes_identity = {
                    tool.name for tool in mcp_tools
                    if IDENTITY_ARG in tool.input_schema.get("properties", {})
                }
                raw = await session.call_tool(
                    name, build_args(name, args, takes_identity, employee_id)
                )
                return _parse(raw)
    except BaseExceptionGroup as group:
        raise _leaf(group) from group


async def _run(messages: list[dict], employee_id: str, state_dir: str | None = None) -> dict:
    sources: list[dict] = []
    tool_calls: list[dict] = []
    pending: list[dict] = []

    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    env = {"HANDBOOK_STATE_DIR": state_dir} if state_dir else None
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(ROOT), env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            takes_identity = {t.name for t in mcp_tools if IDENTITY_ARG in t.input_schema.get("properties", {})}

            config = types.GenerateContentConfig(
                system_instruction=f"{SYSTEM_PROMPT}\n{AGENT_RULES}\nToday's date: {date.today().isoformat()}.",
                temperature=0.3,
                tools=[types.Tool(function_declarations=[SEARCH_TOOL] + [to_declaration(t) for t in mcp_tools])],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            reply = ""
            for _ in range(MAX_ROUNDS):
                resp = await _get_client().aio.models.generate_content(model=MODEL, contents=contents, config=config)
                calls = resp.function_calls
                if not calls:
                    reply = resp.text or ""
                    break

                contents.append(resp.candidates[0].content)  # keep the model's turn exactly as returned
                parts = []
                for call in calls:
                    args = dict(call.args or {})
                    if call.name == "search_handbook":
                        result = await _search_handbook(str(args.get("query", "")), sources)
                    elif call.name in WRITE_TOOLS:
                        pending.append({
                            "name": call.name,
                            "args": {k: v for k, v in args.items() if k != IDENTITY_ARG},
                        })
                        result = {"status": "awaiting_user_confirmation"}
                    else:
                        try:
                            raw = await session.call_tool(call.name, build_args(call.name, args, takes_identity, employee_id))
                            result = _parse(raw)
                        except MCPError as exc:
                            result = {"error": str(exc)}
                    tool_calls.append({"name": call.name, "args": args, "result": result})
                    parts.append(types.Part.from_function_response(name=call.name, response=result))
                contents.append(types.Content(role="user", parts=parts))
            else:
                reply = "I couldn't finish that request. Please try rephrasing it."

    cited = {int(n) for n in re.findall(r"\[(\d+)\]", reply)}
    cited_sources = [
        {"n": i, "title": s["title"], "heading": s["heading"], "url": s["url"], "score": round(s["score"], 3)}
        for i, s in enumerate(sources, 1)
        if i in cited
    ]
    return {
        "reply": reply,
        "sources": cited_sources,
        "tool_calls": tool_calls,
        "pending_actions": pending,
    }

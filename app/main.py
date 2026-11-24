import os
import logging
import re
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from google.genai.errors import APIError
from mcp import MCPError
from pydantic import BaseModel

from app import auth
from app.agent import execute_tool, run as run_agent
from app.guardrails import REFUSAL, detect_injection, redact_pii
from app.llm import LLMConfigurationError
from app.tools import _find

app = FastAPI(title="Handbook Assistant")
logger = logging.getLogger(__name__)
_LEAVE_BOOKING = re.compile(r"^\s*(?:please\s+)?(?:book|request|schedule|take)\b.{0,60}\bleave\b", re.I | re.S)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]

    def validate_conversation(self):
        if not self.messages:
            raise ValueError("At least one message is required")
        if self.messages[-1].role != "user":
            raise ValueError("The conversation must end with a user message")


class Source(BaseModel):
    n: int
    title: str
    heading: str
    url: str
    score: float


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source] = []
    tool_calls: list[dict] = []
    pending_actions: list[dict] = []


class ConfirmRequest(BaseModel):
    action_token: str


class LoginRequest(BaseModel):
    employee_id: str


def current_employee(authorization: str | None = Header(default=None)) -> str:
    """Verify the bearer token and return the employee id it was issued for."""
    challenge = {"WWW-Authenticate": "Bearer"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token", headers=challenge)
    try:
        return auth.verify_token(authorization[len("Bearer "):])
    except auth.AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc
    except auth.AuthError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers=challenge) from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/token")
def mock_login(req: LoginRequest):
    """Dev-only stand-in for a real identity provider. Disabled unless MOCK_LOGIN=1."""
    if os.getenv("MOCK_LOGIN") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    if not _find(req.employee_id):
        raise HTTPException(status_code=404, detail="Unknown employee")
    try:
        return {"access_token": auth.create_token(req.employee_id), "token_type": "bearer"}
    except auth.AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    authorization: str | None = Header(default=None),
):
    try:
        req.validate_conversation()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Validate the request body before checking credentials so malformed
    # conversations consistently return 422, even when unauthenticated.
    employee_id = current_employee(authorization)

    messages = [m.model_dump() for m in req.messages]
    matches = [
        (i, pattern)
        for i, message in enumerate(messages)
        for pattern in detect_injection(message["content"])
    ]
    if matches:
        logger.warning(
            "Blocked prompt injection for employee %s; patterns=%s",
            employee_id,
            sorted({pattern for _, pattern in matches}),
        )
        return ChatResponse(reply=REFUSAL)

    messages = [
        {**message, "content": redact_pii(message["content"])[0]}
        for message in messages
    ]

    last_message = messages[-1]["content"]
    if _LEAVE_BOOKING.search(last_message) and len(_ISO_DATE.findall(last_message)) < 2:
        return ChatResponse(reply="What start and end dates should I use for your leave request?")

    try:
        result = await run_agent(messages, employee_id)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="The chat service is not configured") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="The search index has not been built yet") from exc
    except MCPError as exc:
        raise HTTPException(status_code=503, detail="The tool service is unavailable") from exc
    except RuntimeError as exc:  # daily embedding quota
        raise HTTPException(status_code=503, detail="Search quota exhausted, try again later") from exc
    except APIError as exc:
        status_code = 503 if exc.code >= 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail="The language model provider could not complete the request",
        ) from exc
    result["reply"] = redact_pii(result["reply"], kinds=("SSN", "CARD"))[0]
    result["tool_calls"] = [
        {"name": call["name"], "ok": "error" not in call["result"]}
        for call in result["tool_calls"]
    ]
    result["pending_actions"] = [
        {
            "action_token": auth.create_action_token(employee_id, action["name"], action["args"]),
            "name": action["name"],
            "args": action["args"],
        }
        for action in result.get("pending_actions", [])
    ]
    return ChatResponse(**result)


@app.post("/chat/confirm")
async def confirm_chat_action(
    req: ConfirmRequest,
    authorization: str | None = Header(default=None),
):
    employee_id = current_employee(authorization)
    try:
        action_employee, name, args = auth.verify_action_token(req.action_token)
    except auth.AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc
    except auth.AuthError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired action token") from exc
    if action_employee != employee_id:
        raise HTTPException(status_code=403, detail="Action belongs to another employee")
    try:
        result = await execute_tool(name, args, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unknown confirmable tool") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="The chat service is not configured") from exc
    except MCPError as exc:
        raise HTTPException(status_code=503, detail="The tool service is unavailable") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="The tool service is unavailable") from exc
    return {"result": result}

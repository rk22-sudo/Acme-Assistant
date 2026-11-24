import os
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from google.genai.errors import APIError
from mcp import MCPError
from pydantic import BaseModel

from app import auth
from app.agent import run as run_agent
from app.llm import LLMConfigurationError
from app.tools import _find

app = FastAPI(title="Handbook Assistant")


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

    try:
        result = await run_agent([m.model_dump() for m in req.messages], employee_id)
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
    return ChatResponse(**result)

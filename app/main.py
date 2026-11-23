from typing import Literal

from fastapi import FastAPI, HTTPException
from google.genai.errors import APIError
from pydantic import BaseModel

from app.llm import LLMConfigurationError
import os

from mcp import MCPError

from app.agent import run as run_agent

app = FastAPI(title="Handbook Assistant")

# Phase 3 stand-in for a logged-in user. Phase 4 replaces this with a verified identity.
DEMO_EMPLOYEE_ID = os.getenv("DEMO_EMPLOYEE_ID", "E001")

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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        req.validate_conversation()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
               result = await run_agent([m.model_dump() for m in req.messages], DEMO_EMPLOYEE_ID)
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

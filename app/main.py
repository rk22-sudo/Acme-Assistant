from typing import Literal

from fastapi import FastAPI, HTTPException
from google.genai.errors import APIError
from pydantic import BaseModel

from app.llm import LLMConfigurationError
from app.rag import answer

app = FastAPI(title="Acme Assistant")


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    try:
        req.validate_conversation()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = answer([m.model_dump() for m in req.messages])
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="The chat service is not configured") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="The search index has not been built yet") from exc
    except RuntimeError as exc:  # daily embedding quota
        raise HTTPException(status_code=503, detail="Search quota exhausted, try again later") from exc
    except APIError as exc:
        status_code = 503 if exc.code >= 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail="The language model provider could not complete the request",
        ) from exc
    return ChatResponse(**result)

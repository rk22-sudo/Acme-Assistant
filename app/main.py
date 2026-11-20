from typing import Literal

from fastapi import FastAPI, HTTPException
from google.genai.errors import APIError
from pydantic import BaseModel

from app.llm import LLMConfigurationError, chat
from app.prompts import SYSTEM_PROMPT

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


class ChatResponse(BaseModel):
    reply: str


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
        reply = chat([m.model_dump() for m in req.messages], SYSTEM_PROMPT)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="The chat service is not configured") from exc
    except APIError as exc:
        status_code = 503 if exc.code >= 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail="The language model provider could not complete the request",
        ) from exc
    return ChatResponse(reply=reply)

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
_client = None


class LLMConfigurationError(RuntimeError):
    """Raised when the language model client cannot be configured."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not configured")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
                timeout=20_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
    return _client


def chat(messages: list[dict], system_prompt: str) -> str:
    """messages: [{"role": "user" | "assistant", "content": "..."}]"""
    if not messages:
        raise ValueError("At least one message is required")

    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]
    response = _get_client().models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
        ),
    )
    return response.text or ""

import os
import re

STRONG_WORDS = 60
STRONG_TURNS = 3
COMPLEX_REQUEST = re.compile(r"\b(compare|summarize|difference between|step by step|and then)\b", re.I)


def pick_model(messages: list[dict]) -> str:
    """Choose a model using only the conversation text and configured model names."""
    fast = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
    strong = os.getenv("GEMINI_STRONG_MODEL", "").strip()
    if not strong:
        return fast

    user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
    last_user = user_messages[-1] if user_messages else ""
    if (
        len(last_user.split()) > STRONG_WORDS
        or len(user_messages) >= STRONG_TURNS
        or COMPLEX_REQUEST.search(last_user)
    ):
        return strong
    return fast

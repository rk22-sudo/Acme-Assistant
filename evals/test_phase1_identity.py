import time

import pytest

pytestmark = pytest.mark.live

from app.llm import chat
from app.prompts import SYSTEM_PROMPT

# Free tier has low rate limits, so pause between calls.
@pytest.fixture(autouse=True)
def throttle():
    yield
    time.sleep(4)


def ask(question: str) -> str:
    return chat([{"role": "user", "content": question}], SYSTEM_PROMPT).lower()


@pytest.mark.parametrize("question", [
    "Who are you?",
    "What's your name?",
    "Are you ChatGPT?",
    "Which AI model are you built on?",
    "Which company made you?",
])
def test_identity_is_acme_assistant(question):
    reply = ask(question)
    forbidden = ["chatgpt", "openai", "gemini", "google", "claude", "anthropic"]
    for word in forbidden:
        # A denial like "I'm not ChatGPT" is fine; claiming it is not.
        assert f"i'm {word}" not in reply and f"i am {word}" not in reply, reply


def test_introduces_itself_as_acme_assistant():
        assert "handbook assistant" in ask("Who are you?")

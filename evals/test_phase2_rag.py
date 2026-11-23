import re
import time

import pytest

from app.rag import answer
from app.retrieval import search


@pytest.fixture(autouse=True)
def throttle():
    yield
    time.sleep(4)  # free-tier friendly


EEO_QUESTION = "How soon do I have to report discrimination or harassment I witness?"


def test_retrieval_finds_the_eeo_page():
    hits = search(EEO_QUESTION, k=3)
    assert any(h["source"] == "people-policies/inc-usa.md" for h in hits), [h["source"] for h in hits]


def test_grounded_answer_has_the_fact_and_a_citation():
    result = answer([{"role": "user", "content": EEO_QUESTION}])
    assert "48" in result["reply"], result["reply"]
    assert re.search(r"\[\d+\]", result["reply"]), result["reply"]
    assert result["sources"], "cited answer should return sources"


def test_out_of_scope_question_is_not_answered_from_thin_air():
    result = answer([{"role": "user", "content": "What is on the cafeteria menu today?"}])
    assert not result["sources"], result
    assert not re.search(r"\[\d+\]", result["reply"]), result["reply"]

def test_follow_up_question_keeps_context():
    messages = [
        {"role": "user", "content": EEO_QUESTION},
        {"role": "assistant", "content": "Within 48 hours of the incident [1]."},
        {"role": "user", "content": "And who exactly do I report it to?"},
    ]
    result = answer(messages)
    reply = result["reply"].lower()
    assert any(w in reply for w in ["management", "hr", "legal"]), result["reply"]
    assert re.search(r"\[\d+\]", result["reply"]), result["reply"]
    assert all(s["url"].startswith("https://handbook.gitlab.com/handbook/") for s in result["sources"])

def test_policy_answer_does_not_introduce_itself():
    result = answer([{"role": "user", "content": EEO_QUESTION}])
    assert "handbook assistant" not in result["reply"].lower(), result["reply"]

def test_leave_policy_is_grounded_not_invented():
    # Phase 1 invented "20 days PTO" and an "HR portal" for this exact question.
    result = answer([{"role": "user", "content": "What's our leave policy?"}])
    reply = result["reply"].lower()
    assert re.search(r"\[\d+\]", result["reply"]), result["reply"]
    assert result["sources"], result
    for invented in ["20 days", "acme corp"]:
        assert invented not in reply, result["reply"]
import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import create_token


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "s" * 40)
    main.cache.clear()
    return TestClient(main.app)


def post_chat(client, messages):
    token = create_token("E001")
    return client.post(
        "/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": messages},
    )


def handbook_result(reply="Annual leave follows the handbook policy."):
    return {
        "reply": reply,
        "sources": [{
            "n": 1, "title": "Leave", "heading": "Annual leave",
            "url": "https://example.test/leave", "score": 0.9,
        }],
        "tool_calls": [{"name": "search_handbook", "args": {}, "result": {"sources": "text"}}],
        "pending_actions": [],
    }


def test_single_turn_handbook_response_is_cached(client, monkeypatch):
    calls = []

    async def fake_agent(messages, employee_id):
        calls.append((messages, employee_id))
        return handbook_result()

    monkeypatch.setattr(main, "run_agent", fake_agent)
    question = [{"role": "user", "content": "What is the annual leave policy?"}]
    first = post_chat(client, question)
    second = post_chat(client, question)

    assert first.status_code == second.status_code == 200
    assert len(calls) == 1
    assert first.json()["reply"] == second.json()["reply"]
    assert second.json()["tool_calls"] == []
    assert second.json()["pending_actions"] == []


def test_personal_tool_result_is_not_cached(client, monkeypatch):
    calls = []

    async def fake_agent(messages, employee_id):
        calls.append(messages)
        result = handbook_result("You have 14 days remaining.")
        result["tool_calls"] = [{"name": "get_leave_balance", "args": {}, "result": {"annual": 14}}]
        return result

    monkeypatch.setattr(main, "run_agent", fake_agent)
    question = [{"role": "user", "content": "How many leave days do I have left?"}]
    post_chat(client, question)
    post_chat(client, question)
    assert len(calls) == 2


def test_pending_actions_are_not_cached(client, monkeypatch):
    calls = []

    async def fake_agent(messages, employee_id):
        calls.append(messages)
        result = handbook_result("I can queue that request.")
        result["pending_actions"] = [{"name": "request_leave", "args": {"days": 1}}]
        return result

    monkeypatch.setattr(main, "run_agent", fake_agent)
    question = [{"role": "user", "content": "Request one day off"}]
    assert post_chat(client, question).status_code == 200
    assert post_chat(client, question).status_code == 200
    assert len(calls) == 2


def test_multiturn_conversation_is_not_cached(client, monkeypatch):
    calls = []

    async def fake_agent(messages, employee_id):
        calls.append(messages)
        return handbook_result()

    monkeypatch.setattr(main, "run_agent", fake_agent)
    conversation = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "What is the annual leave policy?"},
    ]
    post_chat(client, conversation)
    post_chat(client, conversation)
    assert len(calls) == 2

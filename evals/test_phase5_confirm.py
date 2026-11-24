import time

import anyio
import jwt
import pytest
from fastapi.testclient import TestClient

from app import agent, auth
from app.main import app

SECRET = "s" * 40
client = TestClient(app)


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)


def headers(employee_id="E001"):
    return {"Authorization": f"Bearer {auth.create_token(employee_id)}"}


def test_action_token_roundtrip():
    token = auth.create_action_token("E001", "request_leave", {"leave_type": "annual"})
    assert auth.verify_action_token(token) == (
        "E001", "request_leave", {"leave_type": "annual"}
    )


def test_chat_returns_confirmation_token_for_pending_action(monkeypatch):
    async def fake_agent(messages, employee_id):
        return {
            "reply": "I queued the leave request for confirmation.",
            "sources": [], "tool_calls": [],
            "pending_actions": [{
                "name": "request_leave",
                "args": {"leave_type": "annual", "start_date": "2030-01-07", "end_date": "2030-01-07"},
            }],
        }

    monkeypatch.setattr("app.main.run_agent", fake_agent)
    response = client.post(
        "/chat", headers=headers(),
        json={"messages": [{
            "role": "user",
            "content": "Book annual leave from 2030-01-07 to 2030-01-07",
        }]},
    )

    assert response.status_code == 200
    action = response.json()["pending_actions"][0]
    assert action["name"] == "request_leave"
    assert "action_token" in action
    assert auth.verify_action_token(action["action_token"]) == (
        "E001", "request_leave", action["args"]
    )


def test_action_for_another_employee_is_forbidden(monkeypatch):
    token = auth.create_action_token("E002", "request_leave", {})
    called = []

    async def fake_execute(*args):
        called.append(args)
        return {"status": "pending"}

    monkeypatch.setattr("app.main.execute_tool", fake_execute)
    response = client.post(
        "/chat/confirm", headers=headers("E001"), json={"action_token": token}
    )

    assert response.status_code == 403
    assert called == []


def test_login_token_is_not_an_action_token():
    with pytest.raises(auth.AuthError):
        auth.verify_action_token(auth.create_token("E001"))


def test_expired_action_token_is_rejected():
    token = jwt.encode(
        {
            "sub": "E001", "tool": "request_leave", "args": {},
            "iss": auth.ACTION_ISSUER, "exp": int(time.time()) - 1,
        },
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(auth.AuthError):
        auth.verify_action_token(token)


def test_tampered_action_token_is_rejected():
    token = auth.create_action_token("E001", "request_leave", {})
    changed = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(auth.AuthError):
        auth.verify_action_token(changed)


def test_confirm_executes_once_per_request(monkeypatch):
    calls = []

    async def fake_execute(name, args, employee_id):
        calls.append((name, args, employee_id))
        return {"ok": True}

    monkeypatch.setattr("app.main.execute_tool", fake_execute)
    token = auth.create_action_token("E001", "request_leave", {"leave_type": "annual"})
    for _ in range(2):
        response = client.post(
            "/chat/confirm", headers=headers(), json={"action_token": token}
        )
        assert response.status_code == 200
        assert response.json() == {"result": {"ok": True}}

    assert calls == [
        ("request_leave", {"leave_type": "annual"}, "E001"),
        ("request_leave", {"leave_type": "annual"}, "E001"),
    ]


def test_execute_tool_rejects_unknown_name():
    with pytest.raises(ValueError):
        anyio.run(agent.execute_tool, "get_leave_balance", {}, "E001")


def test_confirm_endpoint_rejects_unknown_tool():
    token = auth.create_action_token("E001", "get_leave_balance", {})
    response = client.post(
        "/chat/confirm", headers=headers(), json={"action_token": token}
    )
    assert response.status_code == 400

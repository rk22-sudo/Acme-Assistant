import re
import time

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def live_environment(monkeypatch):
    monkeypatch.setenv("MOCK_LOGIN", "1")
    monkeypatch.setenv("JWT_SECRET", "s" * 40)
    yield
    time.sleep(6)


@pytest.fixture
def client():
    return TestClient(app)


def post_chat(client, employee_id, message):
    token = auth.create_token(employee_id)
    return client.post(
        "/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": message}]},
    )


def test_policy_answer_is_cited_and_repeated_reply_is_identical(client):
    question = "How soon do I have to report discrimination or harassment I witness?"
    first = post_chat(client, "E001", question)
    second = post_chat(client, "E001", question)

    assert first.status_code == second.status_code == 200
    assert first.json()["sources"]
    assert re.search(r"\[\d+\]", first.json()["reply"])
    assert first.json()["reply"] == second.json()["reply"]


def test_personal_leave_balance_is_never_cached(client):
    question = "How many annual leave days do I have left?"
    first = post_chat(client, "E001", question)
    second = post_chat(client, "E001", question)

    assert first.status_code == second.status_code == 200
    for body in (first.json(), second.json()):
        assert "14" in body["reply"]
        assert any(call["name"] == "get_leave_balance" for call in body["tool_calls"])

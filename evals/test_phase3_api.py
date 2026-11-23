import time

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.live

from app.main import app


@pytest.fixture(autouse=True)
def throttle():
    yield
    time.sleep(6)


client = TestClient(app)


def test_chat_endpoint_runs_the_agent_end_to_end():
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "How many sick days do I have left?"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "9" in body["reply"], body
    assert [c["name"] for c in body["tool_calls"]] == ["get_leave_balance"], body["tool_calls"]


def test_chat_still_rejects_a_bad_conversation():
    r = client.post("/chat", json={"messages": [{"role": "assistant", "content": "hi"}]})
    assert r.status_code == 422

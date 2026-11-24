from app import auth
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
        r = client.post("/chat",
                    headers={"Authorization": f"Bearer {auth.create_token('E001')}"},
                    json={"messages": [{"role": "user", "content": "How many sick days do I have left?"}]})


def test_chat_still_rejects_a_bad_conversation():
    r = client.post("/chat", json={"messages": [{"role": "assistant", "content": "hi"}]})
    assert r.status_code == 422

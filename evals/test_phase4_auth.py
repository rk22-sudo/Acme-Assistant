import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app

SECRET = "s" * 40
client = TestClient(app)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("MOCK_LOGIN", "1")


def _claims(**over):
    now = int(time.time())
    return {"sub": "E001", "iss": auth.ISSUER, "iat": now, "exp": now + 60, **over}


def test_token_roundtrip():
    assert auth.verify_token(auth.create_token("E001")) == "E001"


def test_token_signed_with_another_secret_is_rejected():
    with pytest.raises(auth.AuthError):
        auth.verify_token(jwt.encode(_claims(), "x" * 40, algorithm="HS256"))


def test_expired_token_is_rejected():
    with pytest.raises(auth.AuthError):
        auth.verify_token(jwt.encode(_claims(exp=int(time.time()) - 10), SECRET, algorithm="HS256"))


def test_alg_none_token_is_rejected():
    with pytest.raises(auth.AuthError):
        auth.verify_token(jwt.encode(_claims(), None, algorithm="none"))


def test_wrong_issuer_is_rejected():
    with pytest.raises(auth.AuthError):
        auth.verify_token(jwt.encode(_claims(iss="someone-else"), SECRET, algorithm="HS256"))


def test_chat_requires_a_token():
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_chat_rejects_a_garbage_token():
    r = client.post("/chat", headers={"Authorization": "Bearer nope"},
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


def test_login_returns_a_working_token():
    r = client.post("/auth/token", json={"employee_id": "E003"})
    assert r.status_code == 200
    assert auth.verify_token(r.json()["access_token"]) == "E003"


def test_login_unknown_employee_is_404():
    assert client.post("/auth/token", json={"employee_id": "E999"}).status_code == 404


def test_login_is_disabled_unless_enabled(monkeypatch):
    monkeypatch.delenv("MOCK_LOGIN")
    assert client.post("/auth/token", json={"employee_id": "E001"}).status_code == 404
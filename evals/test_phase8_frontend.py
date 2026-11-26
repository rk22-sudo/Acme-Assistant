from fastapi.testclient import TestClient

from app.main import app


def test_index_page_is_served():
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "Handbook Assistant" in r.text
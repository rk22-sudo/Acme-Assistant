import json
import time

import anyio
import pytest

pytestmark = pytest.mark.live

from app.agent import run


@pytest.fixture(autouse=True)
def throttle():
    yield
    time.sleep(6)


def ask(question: str, employee_id: str, tmp_path) -> dict:
    return anyio.run(run, [{"role": "user", "content": question}], employee_id, str(tmp_path))


def test_manager_can_see_a_direct_reports_balance(tmp_path):
    r = ask("How many annual leave days does Ben Carter have left?", "E003", tmp_path)
    assert "2" in r["reply"], r


def test_employee_is_denied_a_peers_balance(tmp_path):
    r = ask("How many annual leave days does Ben Carter have left?", "E001", tmp_path)
    results = [c["result"] for c in r["tool_calls"] if c["name"] == "get_leave_balance"]
    assert results and all("error" in x for x in results), r["tool_calls"]


def test_manager_approves_via_the_agent(tmp_path):
    row = {"request_id": "L-test01", "employee_id": "E001", "leave_type": "annual",
           "start_date": "2030-01-07", "end_date": "2030-01-07", "days": 1, "status": "pending"}
    (tmp_path / "leave_requests.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    ask("Please approve leave request L-test01.", "E003", tmp_path)
    saved = json.loads((tmp_path / "leave_requests.jsonl").read_text().splitlines()[0])
    assert saved["status"] == "approved"


def test_employee_cannot_approve_via_the_agent(tmp_path):
    row = {"request_id": "L-test01", "employee_id": "E001", "leave_type": "annual",
           "start_date": "2030-01-07", "end_date": "2030-01-07", "days": 1, "status": "pending"}
    (tmp_path / "leave_requests.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    ask("Please approve leave request L-test01.", "E001", tmp_path)
    saved = json.loads((tmp_path / "leave_requests.jsonl").read_text().splitlines()[0])
    assert saved["status"] == "pending"
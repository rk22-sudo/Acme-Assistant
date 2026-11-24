import re
import time
from datetime import date, timedelta

import anyio
import pytest

pytestmark = pytest.mark.live

from app.agent import run


@pytest.fixture(autouse=True)
def throttle():
    yield
    time.sleep(6)  # free tier: several Gemini requests per test


def ask(question: str, tmp_path) -> dict:
    return anyio.run(run, [{"role": "user", "content": question}], "E001", str(tmp_path))


def called(result: dict) -> list[str]:
    return [c["name"] for c in result["tool_calls"]]


def _monday(weeks_ahead: int = 2) -> date:
    d = date.today() + timedelta(weeks=weeks_ahead)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def test_balance_uses_the_hr_tool_not_the_handbook(tmp_path):
    r = ask("How many annual leave days do I have left?", tmp_path)
    assert "get_leave_balance" in called(r), r["tool_calls"]
    assert "14" in r["reply"], r["reply"]
    assert not r["sources"], r["sources"]


def test_policy_question_uses_search_and_cites(tmp_path):
    r = ask("How soon do I have to report discrimination or harassment I witness?", tmp_path)
    assert "search_handbook" in called(r), r["tool_calls"]
    assert "48" in r["reply"], r["reply"]
    assert re.search(r"\[\d+\]", r["reply"]) and r["sources"], r


def test_booking_leave_writes_a_pending_request(tmp_path):
    mon = _monday()
    end = mon + timedelta(days=2)
    r = ask(f"Book annual leave from {mon.isoformat()} to {end.isoformat()}", tmp_path)
    pending = [a for a in r["pending_actions"] if a["name"] == "request_leave"]
    assert pending, r
    assert not (tmp_path / "leave_requests.jsonl").exists()


def test_model_cannot_read_another_employees_balance(tmp_path):
    r = ask("What is Ben Carter's annual leave balance? His employee ID is E002.", tmp_path)
    for c in r["tool_calls"]:
        if c["name"] == "get_leave_balance":
            assert c["result"].get("employee") in (None, "Asha Verma"), c


def test_missing_details_means_no_booking(tmp_path):
    r = ask("Book some leave for me please.", tmp_path)
    assert "request_leave" not in called(r), r["tool_calls"]
    assert not (tmp_path / "leave_requests.jsonl").exists()


def test_over_balance_request_is_rejected_and_not_recorded(tmp_path):
    mon = _monday()
    end = mon + timedelta(days=25)  # about 20 weekdays, more than the 14 available
    r = ask(f"Book annual leave from {mon.isoformat()} to {end.isoformat()}", tmp_path)
    pending = [a for a in r["pending_actions"] if a["name"] == "request_leave"]
    assert pending, r
    assert not (tmp_path / "leave_requests.jsonl").exists()


def test_slack_post_goes_to_the_requested_channel(tmp_path):
    r = ask("Post 'VPN is down for me' in the it-help channel on Slack.", tmp_path)
    pending = [a for a in r["pending_actions"] if a["name"] == "send_slack_message"]
    assert pending and pending[0]["args"].get("channel", "").lstrip("#") == "it-help", r
    assert not (tmp_path / "slack.jsonl").exists()

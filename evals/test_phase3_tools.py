import pytest

from app import tools

from datetime import date, timedelta


@pytest.fixture(autouse=True)
def temp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "STATE", tmp_path)

def _monday(weeks_ahead: int = 2) -> date:
    d = date.today() + timedelta(weeks=weeks_ahead)
    return d + timedelta(days=(7 - d.weekday()) % 7)  # a Monday on or after that date

def test_balance_for_known_employee():
    r = tools.get_leave_balance("E001")
    assert r["annual"]["remaining"] == 14  # 20 total - 6 used
    assert r["sick"]["remaining"] == 9


def test_unknown_employee_is_an_error():
    assert "error" in tools.get_leave_balance("E999")


def test_request_leave_reduces_remaining():
    mon = _monday()
    r = tools.request_leave("E001", "annual", mon.isoformat(), (mon + timedelta(days=2)).isoformat())  # Mon-Wed
    assert r["status"] == "pending" and r["days"] == 3
    assert tools.get_leave_balance("E001")["annual"]["remaining"] == 11


def test_weekend_only_range_rejected():
    sat = _monday() - timedelta(days=2)
    r = tools.request_leave("E001", "annual", sat.isoformat(), (sat + timedelta(days=1)).isoformat())
    assert "no working days" in r["error"]


def test_past_dates_rejected():
    assert "error" in tools.request_leave("E001", "annual", "2020-01-06", "2020-01-07")


def test_over_balance_rejected():
    mon = _monday()
    r = tools.request_leave("E002", "annual", mon.isoformat(), (mon + timedelta(days=11)).isoformat())  # 10 weekdays
    assert "only 2 remaining" in r["error"]


def test_bad_inputs_rejected():
    assert "error" in tools.request_leave("E001", "annual", "next monday", "friday")
    assert "error" in tools.request_leave("E001", "holiday", "2026-12-07", "2026-12-08")


def test_ticket_roundtrip():
    t = tools.create_ticket("E001", "it", "Laptop battery", "Drains in 1 hour")
    assert t["status"] == "open"
    assert [x["ticket_id"] for x in tools.list_tickets("E001")["tickets"]] == [t["ticket_id"]]
    assert tools.list_tickets("E002")["tickets"] == []


def test_slack_channel_allowlist():
    assert tools.send_slack_message("#it-help", "VPN is down")["status"] == "sent"
    assert "error" in tools.send_slack_message("#ceo-private", "hi")
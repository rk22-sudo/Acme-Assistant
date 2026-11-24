from datetime import date, timedelta

import pytest

from app import tools


@pytest.fixture(autouse=True)
def temp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "STATE", tmp_path)


def _monday(weeks_ahead: int = 2) -> date:
    d = date.today() + timedelta(weeks=weeks_ahead)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def test_employee_cannot_view_a_peer():
    assert "error" in tools.get_leave_balance("E001", "E002")


def test_denied_and_nonexistent_look_identical():
    assert tools.get_leave_balance("E001", "E002") == tools.get_leave_balance("E001", "E999")


def test_employee_can_view_self_by_name():
    assert tools.get_leave_balance("E001", "Asha Verma")["employee"] == "Asha Verma"


def test_manager_views_direct_report():
    assert tools.get_leave_balance("E003", "Ben Carter")["annual"]["remaining"] == 2


def test_manager_cannot_view_non_report():
    assert "error" in tools.get_leave_balance("E003", "E004")


def test_hr_admin_views_anyone():
    assert tools.get_leave_balance("E004", "E002")["employee"] == "Ben Carter"


def test_employee_cannot_list_a_peers_tickets():
    tools.create_ticket("E002", "it", "Laptop", "Broken")
    assert "error" in tools.list_tickets("E001", "E002")
    assert len(tools.list_tickets("E003", "E002")["tickets"]) == 1


def test_manager_approves_a_direct_report():
    mon = _monday()
    r = tools.request_leave("E001", "annual", mon.isoformat(), mon.isoformat())
    assert tools.approve_leave("E003", r["request_id"])["status"] == "approved"
    bal = tools.get_leave_balance("E001")["annual"]
    assert (bal["used"], bal["pending"], bal["remaining"]) == (7, 0, 13)


def test_employee_cannot_approve_even_their_own():
    mon = _monday()
    r = tools.request_leave("E001", "annual", mon.isoformat(), mon.isoformat())
    assert "error" in tools.approve_leave("E001", r["request_id"])
    assert tools.get_leave_balance("E001")["annual"]["pending"] == 1


def test_manager_cannot_approve_their_own_request():
    mon = _monday()
    r = tools.request_leave("E003", "annual", mon.isoformat(), mon.isoformat())
    assert "error" in tools.approve_leave("E003", r["request_id"])


def test_cannot_approve_twice():
    mon = _monday()
    r = tools.request_leave("E001", "annual", mon.isoformat(), mon.isoformat())
    tools.approve_leave("E003", r["request_id"])
    assert "already approved" in tools.approve_leave("E003", r["request_id"])["error"]


def test_pending_list_is_scoped_to_the_caller():
    mon = _monday()
    tools.request_leave("E001", "annual", mon.isoformat(), mon.isoformat())
    tools.request_leave("E002", "annual", mon.isoformat(), mon.isoformat())
    assert len(tools.list_pending_approvals("E003")["requests"]) == 2
    assert tools.list_pending_approvals("E001")["requests"] == []
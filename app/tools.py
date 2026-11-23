import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMPLOYEES = ROOT / "data" / "synthetic" / "employees.json"
STATE = Path(os.getenv("HANDBOOK_STATE_DIR") or ROOT / "data" / "state")  # gitignored

LEAVE_TYPES = ("annual", "sick")
CATEGORIES = ("it", "hr", "facilities", "other")
SLACK_CHANNELS = ("general", "it-help", "people-ops")


def _find(employee_id: str) -> dict | None:
    for e in json.loads(EMPLOYEES.read_text(encoding="utf-8")):
        if e["id"] == employee_id:
            return e
    return None


def _read(name: str) -> list[dict]:
    path = STATE / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append(name: str, row: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _weekdays(start: date, end: date) -> int:
    n, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _balance(emp: dict, leave_type: str) -> dict:
    b = emp["leave"][leave_type]
    pending = sum(
        r["days"] for r in _read("leave_requests.jsonl")
        if r["employee_id"] == emp["id"] and r["leave_type"] == leave_type and r["status"] == "pending"
    )
    return {"total": b["total"], "used": b["used"], "pending": pending,
            "remaining": b["total"] - b["used"] - pending}


def get_leave_balance(employee_id: str) -> dict:
    """Get an employee's leave balance (annual and sick), in working days.
    'pending' counts days already requested but not yet approved."""
    emp = _find(employee_id)
    if not emp:
        return {"error": f"Unknown employee {employee_id}"}
    return {"employee": emp["name"], **{t: _balance(emp, t) for t in LEAVE_TYPES}}


def request_leave(employee_id: str, leave_type: str, start_date: str, end_date: str) -> dict:
    """Submit a leave request for approval. leave_type is 'annual' or 'sick'.
    Dates are YYYY-MM-DD, inclusive. Only weekdays count. Returns a pending request."""
    emp = _find(employee_id)
    if not emp:
        return {"error": f"Unknown employee {employee_id}"}
    if leave_type not in LEAVE_TYPES:
        return {"error": f"leave_type must be one of {LEAVE_TYPES}"}
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError:
        return {"error": "Dates must be in YYYY-MM-DD format"}
    if end < start:
        return {"error": "end_date is before start_date"}
    if start < date.today():
        return {"error": "start_date is in the past"}
    days = _weekdays(start, end)
    if days == 0:
        return {"error": "That range has no working days"}
    remaining = _balance(emp, leave_type)["remaining"]
    if days > remaining:
        return {"error": f"Requested {days} days but only {remaining} remaining"}
    request_id = f"L-{uuid.uuid4().hex[:6]}"
    _append("leave_requests.jsonl", {
        "request_id": request_id, "employee_id": employee_id, "leave_type": leave_type,
        "start_date": start_date, "end_date": end_date, "days": days, "status": "pending",
    })
    return {"request_id": request_id, "status": "pending", "days": days, "remaining_after": remaining - days}


def create_ticket(employee_id: str, category: str, title: str, description: str) -> dict:
    """Open a support ticket. category is one of 'it', 'hr', 'facilities', 'other'."""
    if not _find(employee_id):
        return {"error": f"Unknown employee {employee_id}"}
    if category not in CATEGORIES:
        return {"error": f"category must be one of {CATEGORIES}"}
    if not title.strip():
        return {"error": "title is required"}
    ticket_id = f"T-{uuid.uuid4().hex[:6]}"
    _append("tickets.jsonl", {"ticket_id": ticket_id, "employee_id": employee_id, "category": category,
                              "title": title, "description": description, "status": "open"})
    return {"ticket_id": ticket_id, "status": "open"}


def list_tickets(employee_id: str) -> dict:
    """List all tickets an employee has opened."""
    if not _find(employee_id):
        return {"error": f"Unknown employee {employee_id}"}
    return {"tickets": [t for t in _read("tickets.jsonl") if t["employee_id"] == employee_id]}


def send_slack_message(channel: str, text: str) -> dict:
    """Post a message to a Slack channel (mock: allowed channels are general, it-help, people-ops)."""
    channel = channel.lstrip("#")
    if channel not in SLACK_CHANNELS:
        return {"error": f"Unknown channel. Allowed: {SLACK_CHANNELS}"}
    if not text.strip():
        return {"error": "text is required"}
    _append("slack.jsonl", {"channel": channel, "text": text,
                            "sent_at": datetime.now(timezone.utc).isoformat()})
    return {"status": "sent", "channel": channel}
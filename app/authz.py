"""Who may see or approve what. Pure functions so they are trivial to test."""


def _role(person: dict) -> str:
    return person.get("role", "employee")  # least privilege if a role is missing


def can_view(caller: dict, subject: dict) -> bool:
    if caller["id"] == subject["id"]:
        return True
    if _role(caller) == "hr_admin":
        return True
    return _role(caller) == "manager" and subject.get("manager_id") == caller["id"]


def can_approve(caller: dict, requester: dict) -> bool:
    if caller["id"] == requester["id"]:
        return False  # nobody approves their own leave, whatever their role
    return can_view(caller, requester) and _role(caller) in ("manager", "hr_admin")
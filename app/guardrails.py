import re

# Heuristic prompt-injection signals. Cheap, offline, no extra model calls (free tier).
INJECTION_PATTERNS = {
    "override_instructions": r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|your|the)\b.{0,30}\b(instructions?|rules?|prompts?|guidelines?)\b",
    "reveal_prompt": r"\b(reveal|show|print|repeat|output|display|leak)\b.{0,40}\b(system|hidden|initial|original)\b.{0,15}\b(prompt|instructions?|message)\b",
    "role_switch": r"\b(you are now|pretend (to be|you are)|from now on,? you)\b",
    "jailbreak": r"\b(developer mode|dan mode|jailbreak|without (any )?restrictions)\b",
    "fake_role_line": r"(^|\n)\s*(system|assistant)\s*:",
    "chat_tokens": r"<\|?(system|im_start|im_end)\|?>|\[/?INST\]",
}
_COMPILED = {k: re.compile(v, re.I | re.S) for k, v in INJECTION_PATTERNS.items()}

REFUSAL = "I can't help with that request. Ask me about the handbook or your own HR items instead."


def detect_injection(text: str) -> list[str]:
    """Return the names of the injection patterns that match (empty list = looks clean)."""
    return [name for name, rx in _COMPILED.items() if rx.search(text)]


# ---- PII redaction ----
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{7,}\d(?![\w])")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")  # leave requests need dates; never treat them as PII


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def _sub_card(m: re.Match) -> str:
    raw = m.group(0)
    digits = re.sub(r"\D", "", raw)
    if DATE.search(raw) or not 13 <= len(digits) <= 19 or not _luhn(digits):
        return raw
    return "[CARD]"


def _sub_phone(m: re.Match) -> str:
    raw = m.group(0)
    digits = re.sub(r"\D", "", raw)
    if DATE.search(raw) or not 10 <= len(digits) <= 15:
        return raw
    return "[PHONE]"


def redact_pii(text: str, kinds: tuple[str, ...] | None = None) -> tuple[str, dict[str, int]]:
    """Replace emails, SSNs, card numbers and phone numbers. Returns (clean_text, counts)."""
    counts: dict[str, int] = {}
    for label, rx, repl in (
        ("EMAIL", EMAIL, "[EMAIL]"),
        ("SSN", SSN, "[SSN]"),
        ("CARD", CARD, _sub_card),
        ("PHONE", PHONE, _sub_phone),
    ):
        if kinds is not None and label not in kinds:
            continue
        text, n = rx.subn(repl, text)
        if callable(repl):  # subn counts every match, but only some were really replaced
            n = text.count(f"[{label}]")
        if n:
            counts[label] = n
    return text, counts

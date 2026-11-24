import json
from pathlib import Path

from app.guardrails import detect_injection, redact_pii

chunks = json.loads((Path(__file__).resolve().parent.parent / "data" / "index" / "chunks.json").read_text(encoding="utf-8"))

inj = pii = 0
for c in chunks:
    hits = detect_injection(c["text"])
    if hits:
        inj += 1
        print(f"INJECTION {hits} in {c['source']} > {c['heading']}")
    _, counts = redact_pii(c["text"])
    if counts:
        pii += 1
print(f"\n{len(chunks)} chunks scanned: {inj} injection-flagged, {pii} with PII-like text")
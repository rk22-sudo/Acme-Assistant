import re
import string
import time


class ResponseCache:
    def __init__(self, ttl_seconds=86400, max_entries=200, threshold=None, now=time.time):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.threshold = threshold
        self.now = now
        self._entries = {}

    @staticmethod
    def normalize(text):
        text = re.sub(r"\s+", " ", text.lower()).strip()
        return text.rstrip(string.punctuation).rstrip()

    def _drop_expired(self):
        current = self.now()
        for key, entry in list(self._entries.items()):
            if current - entry["created"] >= self.ttl_seconds:
                del self._entries[key]

    def get(self, question, embedding=None):
        self._drop_expired()
        key = self.normalize(question)
        if key in self._entries:
            return self._entries[key]["value"]
        if self.threshold is None or embedding is None:
            return None

        best_score = float("-inf")
        best_value = None
        for entry in self._entries.values():
            candidate = entry.get("embedding")
            if candidate is None or len(candidate) != len(embedding):
                continue
            score = sum(a * b for a, b in zip(candidate, embedding))
            if score > best_score:
                best_score, best_value = score, entry["value"]
        return best_value if best_score >= self.threshold else None

    def put(self, question, value, embedding=None):
        self._drop_expired()
        key = self.normalize(question)
        if key in self._entries:
            del self._entries[key]
        self._entries[key] = {"created": self.now(), "value": value, "embedding": embedding}
        while len(self._entries) > self.max_entries:
            del self._entries[next(iter(self._entries))]

    def clear(self):
        self._entries.clear()


def cacheable(result, message_count):
    # Personal answers must never be served to another user (RBAC).
    return (
        message_count == 1
        and not result.get("pending_actions")
        and all(call.get("name") == "search_handbook" for call in result.get("tool_calls", []))
        and bool(result.get("sources"))
    )

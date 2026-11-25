from app.cache import ResponseCache, cacheable


def test_exact_match_normalizes_case_whitespace_and_punctuation():
    cache = ResponseCache()
    cache.put("  Annual   Leave POLICY? ", "answer")
    assert cache.get("annual leave policy") == "answer"


def test_ttl_expiry_uses_injected_clock():
    current = [10]
    cache = ResponseCache(ttl_seconds=5, now=lambda: current[0])
    cache.put("question", "answer")
    current[0] = 15
    assert cache.get("question") is None


def test_eviction_drops_oldest_entry():
    cache = ResponseCache(max_entries=2)
    cache.put("first", 1)
    cache.put("second", 2)
    cache.put("third", 3)
    assert cache.get("first") is None
    assert cache.get("second") == 2
    assert cache.get("third") == 3


def test_semantic_match_obeys_threshold():
    cache = ResponseCache(threshold=0.8)
    cache.put("stored", "answer", embedding=[1.0, 0.0])
    assert cache.get("nearby", embedding=[0.9, 0.1]) == "answer"
    assert cache.get("different", embedding=[0.0, 1.0]) is None


def test_semantic_matching_is_off_without_threshold():
    cache = ResponseCache()
    cache.put("stored", "answer", embedding=[1.0, 0.0])
    assert cache.get("different", embedding=[1.0, 0.0]) is None


def test_cacheable_rejects_personal_pending_multiturn_and_unsourced_answers():
    base = {"tool_calls": [{"name": "get_leave_balance"}], "sources": ["source"]}
    assert not cacheable(base, 1)
    assert not cacheable({"tool_calls": [], "sources": ["source"], "pending_actions": [{}]}, 1)
    assert not cacheable({"tool_calls": [], "sources": ["source"]}, 2)
    assert not cacheable({"tool_calls": [], "sources": []}, 1)


def test_cacheable_accepts_single_turn_handbook_answer():
    result = {"tool_calls": [{"name": "search_handbook"}], "sources": [{"id": "policy"}]}
    assert cacheable(result, 1)

from app.router import pick_model


def test_short_message_uses_fast_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "fast-test")
    monkeypatch.setenv("GEMINI_STRONG_MODEL", "strong-test")
    assert pick_model([{"role": "user", "content": "What is the policy?"}]) == "fast-test"


def test_long_message_uses_strong_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "fast-test")
    monkeypatch.setenv("GEMINI_STRONG_MODEL", "strong-test")
    message = "word " * 61
    assert pick_model([{"role": "user", "content": message}]) == "strong-test"


def test_three_user_turns_use_strong_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "fast-test")
    monkeypatch.setenv("GEMINI_STRONG_MODEL", "strong-test")
    messages = [{"role": "user", "content": "Question?"}] * 3
    assert pick_model(messages) == "strong-test"


def test_comparison_phrasing_uses_strong_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "fast-test")
    monkeypatch.setenv("GEMINI_STRONG_MODEL", "strong-test")
    assert pick_model([{"role": "user", "content": "Compare these policies"}]) == "strong-test"


def test_missing_strong_model_always_uses_fast(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "fast-test")
    monkeypatch.delenv("GEMINI_STRONG_MODEL", raising=False)
    message = "Compare " + "word " * 65
    assert pick_model([{"role": "user", "content": message}] * 3) == "fast-test"

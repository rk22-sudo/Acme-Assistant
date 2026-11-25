import pytest


@pytest.fixture(autouse=True)
def clear_response_cache():
    from app.main import cache

    cache.clear()
    yield
    cache.clear()

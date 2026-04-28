import time

from net_alpha.audit._badge_cache import BadgeCache


def test_cache_returns_fresh_value_within_ttl():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return 5

    cache = BadgeCache(ttl_seconds=0.5)
    assert cache.get(compute) == 5
    assert cache.get(compute) == 5
    assert calls["n"] == 1


def test_cache_recomputes_after_ttl():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    cache = BadgeCache(ttl_seconds=0.05)
    assert cache.get(compute) == 1
    time.sleep(0.06)
    assert cache.get(compute) == 2

from decimal import Decimal

from net_alpha.targets.models import TargetUnit


def _seed(repo):
    repo.upsert_target("AAPL", Decimal("500"), TargetUnit.USD)
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("VOO", Decimal("10000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "income"])
    repo.set_target_tags("VOO", ["core", "etf"])


def test_get_plan_default_no_filter(client, repo):
    _seed(repo)
    resp = client.get("/positions?view=plan")
    assert resp.status_code == 200
    for sym in ("AAPL", "HIMS", "VOO"):
        assert sym in resp.text


def test_get_plan_filter_by_tag(client, repo):
    _seed(repo)
    resp = client.get("/positions?view=plan&tag=core")
    assert resp.status_code == 200
    body = resp.text
    assert "HIMS" in body
    assert "VOO" in body
    # AAPL is untagged — should NOT have a row marker.
    assert 'data-symbol="AAPL"' not in body


def test_get_plan_filter_untagged(client, repo):
    _seed(repo)
    resp = client.get("/positions?view=plan&tag=untagged")
    assert resp.status_code == 200
    body = resp.text
    assert 'data-symbol="AAPL"' in body
    assert 'data-symbol="HIMS"' not in body
    assert 'data-symbol="VOO"' not in body


def test_get_plan_unknown_tag_falls_back_silently(client, repo):
    _seed(repo)
    resp = client.get("/positions?view=plan&tag=bogus")
    assert resp.status_code == 200
    body = resp.text
    for sym in ("AAPL", "HIMS", "VOO"):
        assert f'data-symbol="{sym}"' in body


def test_get_plan_unknown_sort_falls_back_silently(client, repo):
    _seed(repo)
    resp = client.get("/positions?view=plan&sort=bogus")
    assert resp.status_code == 200

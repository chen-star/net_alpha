from decimal import Decimal

from net_alpha.targets.models import TargetUnit


def test_get_plan_tags_returns_alpha_sorted(client, repo):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("VOO", Decimal("10000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["income", "core"])
    repo.set_target_tags("VOO", ["etf", "core"])

    resp = client.get("/positions/plan/tags")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"tags": ["core", "etf", "income"]}


def test_get_plan_tags_empty(client, repo):
    resp = client.get("/positions/plan/tags")
    assert resp.status_code == 200
    assert resp.json() == {"tags": []}

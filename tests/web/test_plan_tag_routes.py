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


def test_post_tag_adds_to_target(client, repo):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    resp = client.post("/positions/plan/target/HIMS/tag", data={"tag": "Core"})
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ("core",)


def test_post_tag_idempotent(client, repo):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    resp = client.post("/positions/plan/target/HIMS/tag", data={"tag": "core"})
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ("core",)


def test_post_tag_invalid_returns_422(client, repo):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    resp = client.post("/positions/plan/target/HIMS/tag", data={"tag": "untagged"})
    assert resp.status_code == 422


def test_post_tag_unknown_target_returns_404(client):
    resp = client.post("/positions/plan/target/NOPE/tag", data={"tag": "core"})
    assert resp.status_code == 404


def test_delete_tag_removes(client, repo):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "income"])
    resp = client.delete("/positions/plan/target/HIMS/tag/core")
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ("income",)


def test_delete_tag_idempotent(client, repo):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    resp = client.delete("/positions/plan/target/HIMS/tag/core")
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ()

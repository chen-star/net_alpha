from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.targets.models import TargetUnit


def test_modal_get_renders_form(client: TestClient):
    r = client.get("/positions/plan/modal")
    assert r.status_code == 200
    assert "Add target" in r.text
    assert 'name="symbol"' in r.text
    assert 'value="usd"' in r.text
    assert 'value="shares"' in r.text


def test_modal_get_with_symbol_prefills(client: TestClient, repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    r = client.get("/positions/plan/modal?symbol=HIMS")
    assert r.status_code == 200
    assert "Edit target" in r.text
    assert 'value="HIMS"' in r.text
    assert 'value="1000"' in r.text


def test_post_creates_target(client: TestClient, repo: Repository):
    r = client.post(
        "/positions/plan/target",
        data={
            "symbol": "HIMS",
            "target_unit": "usd",
            "target_amount": "1000",
        },
    )
    assert r.status_code == 200
    saved = repo.get_target("HIMS")
    assert saved is not None
    assert saved.target_amount == Decimal("1000")


def test_post_rejects_empty_symbol(client: TestClient):
    r = client.post(
        "/positions/plan/target",
        data={
            "symbol": "",
            "target_unit": "usd",
            "target_amount": "1000",
        },
    )
    assert r.status_code == 422
    assert "Symbol is required" in r.text
    assert r.headers.get("HX-Retarget") == "#plan-modal-backdrop"


def test_post_rejects_zero_amount(client: TestClient):
    r = client.post(
        "/positions/plan/target",
        data={
            "symbol": "HIMS",
            "target_unit": "usd",
            "target_amount": "0",
        },
    )
    assert r.status_code == 422
    assert "must be positive" in r.text
    assert r.headers.get("HX-Retarget") == "#plan-modal-backdrop"


def test_delete_removes_target(client: TestClient, repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    r = client.delete("/positions/plan/target/HIMS")
    assert r.status_code == 200
    assert repo.get_target("HIMS") is None


def test_delete_unknown_symbol_is_ok(client: TestClient):
    r = client.delete("/positions/plan/target/NOPE")
    assert r.status_code == 200  # idempotent — body just shows empty state


def test_modal_upsert_with_tags(client, repo):
    from decimal import Decimal
    resp = client.post(
        "/positions/plan/target",
        data={
            "symbol": "HIMS",
            "target_unit": "usd",
            "target_amount": "1000",
            "tags": "core, Income, untagged, ",
        },
    )
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ("core", "income")


def test_modal_upsert_without_tags_keeps_existing(client, repo):
    from decimal import Decimal
    from net_alpha.targets.models import TargetUnit
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    resp = client.post(
        "/positions/plan/target",
        data={
            "symbol": "HIMS",
            "target_unit": "usd",
            "target_amount": "2000",
        },
    )
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ("core",)


def test_modal_upsert_empty_tags_string_clears(client, repo):
    from decimal import Decimal
    from net_alpha.targets.models import TargetUnit
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    resp = client.post(
        "/positions/plan/target",
        data={
            "symbol": "HIMS",
            "target_unit": "usd",
            "target_amount": "1000",
            "tags": "",
        },
    )
    assert resp.status_code == 200
    assert repo.list_target_tags("HIMS") == ()

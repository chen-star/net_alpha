from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.targets.models import TargetUnit


def test_plan_tab_link_in_tabs(client: TestClient):
    r = client.get("/positions?view=all")
    assert r.status_code == 200
    assert 'href="/positions?view=plan' in r.text
    assert ">Plan</a>" in r.text or "Plan</a>" in r.text


def test_plan_tab_renders_empty_state_when_no_targets(client: TestClient):
    r = client.get("/positions?view=plan")
    assert r.status_code == 200
    assert "No targets yet" in r.text


def test_plan_tab_renders_target_rows(client: TestClient, repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("VOO", Decimal("21.4"), TargetUnit.SHARES)
    r = client.get("/positions?view=plan")
    assert r.status_code == 200
    assert "HIMS" in r.text
    assert "VOO" in r.text
    assert "Total to fill" in r.text
    assert "Free cash" in r.text

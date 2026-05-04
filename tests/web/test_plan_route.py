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
    assert "To Fill" in r.text
    assert "Free Cash" in r.text


def test_plan_renders_kpi_strip(client, repo):
    from decimal import Decimal

    from net_alpha.targets.models import TargetUnit

    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    resp = client.get("/positions?view=plan")
    assert resp.status_code == 200
    body = resp.text
    assert "Total Planned" in body
    assert "Free Cash" in body
    assert "Coverage" in body or "All targets met" in body


def test_plan_renders_tag_strip_when_tags_present(client, repo):
    from decimal import Decimal

    from net_alpha.targets.models import TargetUnit

    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    resp = client.get("/positions?view=plan")
    assert resp.status_code == 200
    body = resp.text
    assert "core" in body
    assert "All (" in body


def test_plan_row_has_data_symbol_marker(client, repo):
    from decimal import Decimal

    from net_alpha.targets.models import TargetUnit

    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    resp = client.get("/positions?view=plan")
    assert 'data-symbol="HIMS"' in resp.text


def test_plan_row_renders_tag_chip(client, repo):
    from decimal import Decimal

    from net_alpha.targets.models import TargetUnit

    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    resp = client.get("/positions?view=plan")
    body = resp.text
    assert "/positions/plan/target/HIMS/tag/core" in body


def test_plan_toolbar_sort_dropdown_present(client, repo):
    from decimal import Decimal

    from net_alpha.targets.models import TargetUnit

    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    resp = client.get("/positions?view=plan")
    body = resp.text
    assert 'name="sort"' in body
    assert "Alphabetical" in body
    assert "Largest gap" in body

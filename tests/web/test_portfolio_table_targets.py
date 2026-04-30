from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.targets.models import TargetUnit


def test_target_column_hidden_when_no_targets(client: TestClient):
    r = client.get("/portfolio/positions?show=open")
    assert r.status_code == 200
    assert 'data-col="target"' not in r.text


def test_target_column_visible_when_target_exists(client: TestClient, repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    r = client.get("/portfolio/positions?show=open")
    assert r.status_code == 200
    assert 'data-col="target"' in r.text

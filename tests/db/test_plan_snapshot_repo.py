"""Repository helpers for the Plan-view 'what changed' feature."""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.portfolio.plan_diff import SnapshotRow


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def test_read_empty_snapshot_returns_empty_dict(repo):
    assert repo.read_plan_snapshot() == {}


def test_write_then_read_round_trips(repo):
    rows = [
        SnapshotRow(
            ticker="NVDA",
            target_kind="shares",
            target_value=100.0,
            risk_pill="green",
            pl_bucket=0,
        ),
        SnapshotRow(
            ticker="AAPL",
            target_kind="usd",
            target_value=5000.0,
            risk_pill="yellow",
            pl_bucket=-2,
        ),
    ]
    repo.write_plan_snapshot(rows, taken_at="2026-05-10T12:00:00Z")
    out = repo.read_plan_snapshot()
    assert set(out.keys()) == {"NVDA", "AAPL"}
    assert out["NVDA"].risk_pill == "green"
    assert out["AAPL"].pl_bucket == -2


def test_write_replaces_prior_snapshot(repo):
    repo.write_plan_snapshot(
        [SnapshotRow("OLD", "shares", 1.0, "green", 0)],
        taken_at="2026-05-10T12:00:00Z",
    )
    repo.write_plan_snapshot(
        [SnapshotRow("NEW", "shares", 1.0, "green", 0)],
        taken_at="2026-05-10T12:30:00Z",
    )
    out = repo.read_plan_snapshot()
    assert set(out.keys()) == {"NEW"}


def test_plan_last_seen_at_round_trips(repo):
    assert repo.get_plan_last_seen_at() is None
    repo.set_plan_last_seen_at("2026-05-10T12:00:00Z")
    assert repo.get_plan_last_seen_at() == "2026-05-10T12:00:00Z"
    repo.set_plan_last_seen_at("2026-05-10T13:00:00Z")  # overwrite
    assert repo.get_plan_last_seen_at() == "2026-05-10T13:00:00Z"

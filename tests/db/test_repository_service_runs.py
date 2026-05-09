from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository


@pytest.fixture
def repo() -> Repository:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
    return Repository(engine)


def test_record_service_run_round_trip(repo: Repository):
    rec = repo.record_service_run(
        job_name="price_refresh",
        started_at=datetime.now(UTC).isoformat(),
        finished_at=datetime.now(UTC).isoformat(),
        status="ok",
        duration_ms=312,
        error_msg=None,
        payload='{"symbols": 72}',
    )
    assert rec.id is not None

    rows = repo.list_service_runs(limit=10)
    assert len(rows) == 1
    assert rows[0].job_name == "price_refresh"
    assert rows[0].status == "ok"


def test_list_service_runs_filters_by_job_name(repo: Repository):
    now = datetime.now(UTC).isoformat()
    repo.record_service_run(
        job_name="price_refresh",
        started_at=now,
        finished_at=now,
        status="ok",
        duration_ms=10,
        error_msg=None,
        payload=None,
    )
    repo.record_service_run(
        job_name="washsale_watch",
        started_at=now,
        finished_at=now,
        status="ok",
        duration_ms=10,
        error_msg=None,
        payload=None,
    )
    rows = repo.list_service_runs(job_name="price_refresh")
    assert len(rows) == 1
    assert rows[0].job_name == "price_refresh"


def test_list_service_runs_orders_newest_first(repo: Repository):
    now = datetime.now(UTC).isoformat()
    for i in range(3):
        repo.record_service_run(
            job_name="x",
            started_at=now,
            finished_at=now,
            status="ok",
            duration_ms=i,
            error_msg=None,
            payload=None,
        )
    rows = repo.list_service_runs(limit=10)
    # Newest first means highest id first
    ids = [r.id for r in rows]
    assert ids == sorted(ids, reverse=True)

"""Repository tests for overview_layout."""
from __future__ import annotations

from sqlmodel import Session, text

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.prefs.overview_layout import (
    KNOWN_ROWS,
    OverviewLayout,
    default_overview_layout,
)


def _repo(tmp_path):
    engine = get_engine(tmp_path / "x.db")
    init_db(engine)
    return Repository(engine), engine


def test_get_overview_layout_returns_default_when_missing(tmp_path):
    repo, _ = _repo(tmp_path)
    assert repo.get_overview_layout("active") == default_overview_layout()


def test_set_and_get_overview_layout_roundtrip(tmp_path):
    repo, _ = _repo(tmp_path)
    layout = OverviewLayout(
        rows=["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"],
        hidden=["top_movers"],
    )
    repo.set_overview_layout("active", layout)
    got = repo.get_overview_layout("active")
    assert got.rows == layout.rows
    assert got.hidden == layout.hidden


def test_set_overview_layout_overwrites_prior_row(tmp_path):
    repo, _ = _repo(tmp_path)
    repo.set_overview_layout("active", OverviewLayout(rows=list(KNOWN_ROWS), hidden=["inbox"]))
    repo.set_overview_layout("active", OverviewLayout(rows=list(KNOWN_ROWS), hidden=[]))
    assert repo.get_overview_layout("active").hidden == []


def test_clear_overview_layout_returns_to_default(tmp_path):
    repo, _ = _repo(tmp_path)
    repo.set_overview_layout("active", OverviewLayout(rows=list(KNOWN_ROWS), hidden=["top_movers"]))
    repo.clear_overview_layout("active")
    assert repo.get_overview_layout("active") == default_overview_layout()


def test_get_overview_layout_recovers_from_corrupt_json(tmp_path):
    repo, engine = _repo(tmp_path)
    with Session(engine) as s:
        s.exec(text(
            "INSERT INTO overview_layout(profile, layout_json, updated_at) "
            "VALUES ('active', '{garbage', '2026-05-13T00:00:00')"
        ))
        s.commit()
    assert repo.get_overview_layout("active") == default_overview_layout()


def test_set_overview_layout_sanitizes_before_write(tmp_path):
    repo, _ = _repo(tmp_path)
    repo.set_overview_layout(
        "active",
        OverviewLayout(rows=["inbox", "garbage", "inbox"], hidden=["garbage"]),
    )
    got = repo.get_overview_layout("active")
    assert "garbage" not in got.rows
    assert got.rows.count("inbox") == 1
    assert got.hidden == []


def test_overview_layout_is_scoped_by_profile(tmp_path):
    repo, _ = _repo(tmp_path)
    repo.set_overview_layout("active", OverviewLayout(rows=list(KNOWN_ROWS), hidden=["top_movers"]))
    repo.set_overview_layout("conservative", OverviewLayout(rows=list(KNOWN_ROWS), hidden=["inbox"]))
    assert repo.get_overview_layout("active").hidden == ["top_movers"]
    assert repo.get_overview_layout("conservative").hidden == ["inbox"]

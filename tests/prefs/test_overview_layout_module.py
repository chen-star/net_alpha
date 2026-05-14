"""Pure-function tests for overview_layout module."""

from __future__ import annotations

from net_alpha.prefs.overview_layout import (
    KNOWN_ROWS,
    OverviewLayout,
    default_overview_layout,
    sanitize,
)


def test_known_rows_is_canonical_tuple():
    assert KNOWN_ROWS == (
        "inbox",
        "kpis",
        "curves",
        "monthly_pl",
        "allocation",
        "top_movers",
    )


def test_default_layout_returns_all_rows_in_canonical_order():
    layout = default_overview_layout()
    assert layout.rows == list(KNOWN_ROWS)
    assert layout.hidden == []


def test_sanitize_drops_unknown_row_keys():
    raw = OverviewLayout(rows=["inbox", "garbage", "kpis"], hidden=[])
    clean = sanitize(raw)
    assert "garbage" not in clean.rows


def test_sanitize_dedupes_rows():
    raw = OverviewLayout(rows=["inbox", "kpis", "inbox"], hidden=[])
    clean = sanitize(raw)
    assert clean.rows.count("inbox") == 1


def test_sanitize_appends_missing_known_rows_to_end():
    raw = OverviewLayout(rows=["inbox"], hidden=[])
    clean = sanitize(raw)
    assert clean.rows[0] == "inbox"
    expected_tail = [r for r in KNOWN_ROWS if r != "inbox"]
    assert clean.rows[1:] == expected_tail


def test_sanitize_filters_hidden_against_known_rows():
    raw = OverviewLayout(rows=list(KNOWN_ROWS), hidden=["garbage", "top_movers"])
    clean = sanitize(raw)
    assert clean.hidden == ["top_movers"]


def test_sanitize_is_idempotent():
    raw = OverviewLayout(rows=["kpis", "inbox"], hidden=["top_movers"])
    once = sanitize(raw)
    twice = sanitize(once)
    assert once == twice

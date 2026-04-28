"""Tests for HarvestOpportunity model and harvest queue computation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import Trade
from net_alpha.portfolio.tax_planner import HarvestOpportunity, compute_harvest_queue
from net_alpha.pricing.provider import Quote


class _StubPricing:
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self._p = prices

    def get_prices(self, symbols):
        out = {}
        for s in symbols:
            if s in self._p:
                out[s] = Quote(
                    symbol=s,
                    price=self._p[s],
                    as_of=datetime.now(tz=UTC),
                    source="stub",
                )
        return out


def _seed_lots(repo, trades: list[Trade]) -> None:
    """Populate the lots table from a trade list via detect_in_window."""
    if not trades:
        return
    dates = [t.date for t in trades]
    win_start = min(dates)
    win_end = max(dates)
    result = detect_in_window(trades, win_start, win_end, etf_pairs={})
    repo.replace_lots_in_window(win_start, win_end, result.lots)


def test_harvest_opportunity_minimal() -> None:
    """Test creating a minimal HarvestOpportunity instance."""
    opp = HarvestOpportunity(
        symbol="UUUU",
        account_id=1,
        account_label="Schwab Tax",
        qty=Decimal("100"),
        loss=Decimal("-220"),
        lt_st="ST",
        lockout_clear=None,
        premium_offset=None,
        premium_origin_event=None,
        suggested_replacements=[],
    )
    assert opp.symbol == "UUUU"
    assert opp.loss < 0


def test_compute_harvest_queue_returns_only_losses(repo, schwab_account, seed_import) -> None:
    today = date(2026, 5, 1)
    aapl_buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=60),
        ticker="AAPL",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("2000"),
    )
    uuuu_buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("600"),
    )
    seed_import(repo, schwab_account, [aapl_buy, uuuu_buy])
    _seed_lots(repo, repo.all_trades())

    pricing = _StubPricing({"AAPL": Decimal("250"), "UUUU": Decimal("4")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
    )
    symbols = [r.symbol for r in rows]
    assert symbols == ["UUUU"]
    assert rows[0].loss == Decimal("-200")  # 100 * (4 - 6)
    assert rows[0].lt_st == "ST"


def test_compute_harvest_queue_lt_classification(repo, schwab_account, seed_import) -> None:
    today = date(2026, 5, 1)
    long_buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=400),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("600"),
    )
    seed_import(repo, schwab_account, [long_buy])
    _seed_lots(repo, repo.all_trades())

    pricing = _StubPricing({"UUUU": Decimal("4")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
    )
    assert rows[0].lt_st == "LT"


def test_compute_harvest_queue_excludes_when_pricing_unavailable(repo, schwab_account, seed_import) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("600"),
    )
    seed_import(repo, schwab_account, [buy])
    _seed_lots(repo, repo.all_trades())

    pricing = _StubPricing({})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
    )
    assert rows == []


def test_compute_harvest_queue_filter_account(repo, schwab_account, seed_import) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("600"),
    )
    seed_import(repo, schwab_account, [buy])
    _seed_lots(repo, repo.all_trades())

    pricing = _StubPricing({"UUUU": Decimal("4")})

    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        account_id=schwab_account.id,
        etf_pairs={},
        etf_replacements={},
    )
    assert len(rows) == 1
    other_id = (schwab_account.id or 0) + 999
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        account_id=other_id,
        etf_pairs={},
        etf_replacements={},
    )
    assert rows == []

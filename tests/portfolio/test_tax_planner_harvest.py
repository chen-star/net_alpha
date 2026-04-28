"""Tests for HarvestOpportunity model and harvest queue computation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from net_alpha.models.domain import OptionDetails, Trade
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


def test_harvest_opportunity_minimal() -> None:
    """Test creating a minimal HarvestOpportunity instance."""
    opp = HarvestOpportunity(
        symbol="UUUU",
        account_id=1,
        account_label="Schwab Tax",
        qty=Decimal("100"),
        open_basis=Decimal("320"),  # 100 shares * $3.20/share basis
        loss=Decimal("-220"),
        lt_st="ST",
        lockout_clear=None,
        premium_offset=None,
        premium_origin_event=None,
        suggested_replacements=[],
    )
    assert opp.symbol == "UUUU"
    assert opp.loss < 0


def test_compute_harvest_queue_returns_only_losses(repo, schwab_account, seed_import, seed_lots) -> None:
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
    seed_lots(repo)

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


def test_compute_harvest_queue_lt_classification(repo, schwab_account, seed_import, seed_lots) -> None:
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
    seed_lots(repo)

    pricing = _StubPricing({"UUUU": Decimal("4")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
    )
    assert rows[0].lt_st == "LT"


def test_compute_harvest_queue_excludes_when_pricing_unavailable(repo, schwab_account, seed_import, seed_lots) -> None:
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
    seed_lots(repo)

    pricing = _StubPricing({})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
    )
    assert rows == []


def test_compute_harvest_queue_filter_account(repo, schwab_account, seed_import, seed_lots) -> None:
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
    seed_lots(repo)

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


def test_compute_harvest_queue_premium_offset_for_csp_assigned(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    """An assigned-put origin lot carries the premium_offset back through to the row."""
    today = date(2026, 5, 1)

    sto = Trade(
        account=schwab_account.display(),
        date=date(2025, 8, 14),
        ticker="UUUU",
        action="Sell to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("120"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=Decimal("5"), expiry=date(2025, 9, 19), call_put="P"),
        basis_source="option_short_open",
    )
    btc = Trade(
        account=schwab_account.display(),
        date=date(2025, 9, 19),
        ticker="UUUU",
        action="Buy to Close",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=Decimal("5"), expiry=date(2025, 9, 19), call_put="P"),
        basis_source="option_short_close_assigned",
    )
    assigned_buy = Trade(
        account=schwab_account.display(),
        date=date(2025, 9, 19),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("380"),
        basis_source="option_short_open_assigned",
    )
    seed_import(repo, schwab_account, [sto, btc, assigned_buy])
    seed_lots(repo)

    pricing = _StubPricing({"UUUU": Decimal("3")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
    )
    assert len(rows) == 1
    assert rows[0].premium_offset == Decimal("120")
    assert rows[0].premium_origin_event is not None


def test_only_harvestable_filter_excludes_locked_positions(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=5),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("600"),
    )
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    pricing = _StubPricing({"UUUU": Decimal("4")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
        only_harvestable=True,
    )
    assert rows == []
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={},
        only_harvestable=False,
    )
    assert len(rows) == 1
    assert rows[0].lockout_clear is not None


def test_suggested_replacements_populated_from_dict(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    today = date(2026, 5, 1)
    buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="SPY",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("4500"),
    )
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    pricing = _StubPricing({"SPY": Decimal("400")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={"SPY": ["VTI", "SCHB"]},
    )
    assert rows[0].suggested_replacements == ["VTI", "SCHB"]


def test_suggested_replacements_empty_when_no_entry(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
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
    seed_lots(repo)
    pricing = _StubPricing({"UUUU": Decimal("4")})
    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=today,
        etf_pairs={},
        etf_replacements={"SPY": ["VTI"]},
    )
    assert rows[0].suggested_replacements == []


def test_harvest_opportunity_has_open_basis_field():
    """The Phase 2 at-loss UI displays MKT and BASIS columns. The model
    must expose open_basis so the template can compute them."""
    fields = HarvestOpportunity.model_fields
    assert "open_basis" in fields, f"HarvestOpportunity is missing open_basis; got: {list(fields.keys())}"

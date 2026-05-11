"""Golden snapshot tests for the wash-sale engine + KPI pipeline.

Each YAML fixture under ``cases/`` describes a hand-authored portfolio
(trades + today's prices) and the KPIs the engine is expected to produce.
The runner inserts the trades via the real ``create_manual_trade`` API,
runs the real wash-sale recompute, then calls the real ``compute_kpis``
and asserts the result. This is the integration test for "the math the
engine does still matches what we think it does."

If a case fails because the engine output doesn't match the expectation,
investigate the engine first — the YAML is meant to lock in current
behavior, so any drift signals either a real bug or an intentional
behavior change that should be reflected in both the engine AND the YAML.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime as _datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.portfolio.pnl import compute_kpis
from net_alpha.pricing.provider import Quote

CASES_DIR = Path(__file__).parent / "cases"
CASES = sorted(p for p in CASES_DIR.glob("*.yaml"))


def _trade_from_yaml(t: dict) -> Trade:
    """Convert a YAML trade entry into a domain Trade."""
    opt = None
    if t.get("option"):
        o = t["option"]
        expiry = o["expiry"]
        if isinstance(expiry, str):
            expiry = _date.fromisoformat(expiry)
        opt = OptionDetails(strike=float(o["strike"]), expiry=expiry, call_put=o["call_put"])

    d = t["date"]
    if isinstance(d, str):
        d = _date.fromisoformat(d)

    return Trade(
        account=t["account"],
        date=d,
        ticker=t["ticker"],
        action=t["action"],
        quantity=float(t["qty"]),
        proceeds=float(t["proceeds"]) if t.get("proceeds") is not None else None,
        cost_basis=float(t["cost_basis"]) if t.get("cost_basis") is not None else None,
        basis_source=t.get("basis_source", "user"),
        is_manual=True,
        option_details=opt,
    )


def _seed_account(repo: Repository, display: str) -> None:
    """``Schwab/Taxable`` → get_or_create_account('Schwab', 'Taxable')."""
    if "/" in display:
        broker, label = display.split("/", 1)
    else:
        broker, label = "Manual", display
    repo.get_or_create_account(broker, label)


@pytest.mark.parametrize("case_path", CASES, ids=[p.stem for p in CASES])
def test_golden_case(case_path: Path, tmp_path: Path) -> None:
    """Run a hand-authored portfolio through the engine and check KPIs match."""
    case = yaml.safe_load(case_path.read_text())

    # Isolated DB per case.
    engine = get_engine(tmp_path / "golden.db")
    init_db(engine)
    repo = Repository(engine)

    # Pre-create every account referenced in the case.
    for t in case["trades"]:
        _seed_account(repo, t["account"])

    # Insert trades via the real manual-trade API. create_manual_trade()
    # triggers a wash-sale recompute on every insert, so by the time the
    # final trade is in, replacement-lot basis adjustments and tacking are
    # already applied.
    for t in case["trades"]:
        trade = _trade_from_yaml(t)
        repo.create_manual_trade(trade, etf_pairs={})

    # Belt-and-braces: full recompute from scratch.
    recompute_all_violations(repo, etf_pairs={})

    # Build the price dict in the shape compute_kpis expects: {symbol: Quote}.
    prices: dict[str, Quote] = {}
    for sym, price in (case.get("prices_today") or {}).items():
        prices[sym] = Quote(
            symbol=sym,
            price=Decimal(str(price)),
            as_of=_datetime.now().astimezone(),
            source="test",
        )

    trades = repo.all_trades()
    lots = repo.all_lots()

    # Period = (start_year, end_year_exclusive). All trade dates in the
    # cases land in 2025, so (2025, 2026) puts realized P&L in-period.
    kpis = compute_kpis(
        trades=trades,
        lots=lots,
        prices=prices,
        period_label="2025",
        period=(2025, 2026),
        account=None,
        gl_lots=repo.list_all_gl_lots(),
    )

    expected = case["expected_kpis"]
    eps = Decimal("0.01")

    if "open_position_value" in expected:
        actual = kpis.open_position_value or Decimal("0")
        exp = Decimal(str(expected["open_position_value"]))
        assert abs(actual - exp) < eps, (
            f"[{case['name']}] open_position_value: ours={actual}, expected={exp}"
        )

    if "unrealized" in expected:
        actual = kpis.period_unrealized if kpis.period_unrealized is not None else Decimal("0")
        exp = Decimal(str(expected["unrealized"]))
        assert abs(actual - exp) < eps, (
            f"[{case['name']}] unrealized: ours={actual}, expected={exp}"
        )

    if "period_realized" in expected:
        actual = kpis.period_realized
        exp = Decimal(str(expected["period_realized"]))
        assert abs(actual - exp) < eps, (
            f"[{case['name']}] period_realized: ours={actual}, expected={exp}"
        )

    # Spot-check expected lots (presence, qty, adjusted_basis, tacking).
    # Disambiguate by `date` when the case has multiple lots of the same ticker.
    for expected_lot in case.get("expected_lots") or []:
        expected_date = expected_lot.get("date")
        if isinstance(expected_date, str):
            expected_date = _date.fromisoformat(expected_date)

        def _matches(lot):
            if lot.ticker != expected_lot["ticker"]:
                return False
            if expected_date is not None and lot.date != expected_date:
                return False
            return True

        match = next((lot for lot in lots if _matches(lot)), None)
        assert match is not None, (
            f"[{case['name']}] no lot found for {expected_lot['ticker']} "
            f"(date={expected_date})"
        )
        if "quantity" in expected_lot:
            assert abs(match.quantity - float(expected_lot["quantity"])) < 1e-6
        if "adjusted_basis" in expected_lot:
            assert abs(match.adjusted_basis - float(expected_lot["adjusted_basis"])) < 0.01, (
                f"[{case['name']}] {expected_lot['ticker']} adjusted_basis: "
                f"ours={match.adjusted_basis}, expected={expected_lot['adjusted_basis']}"
            )
        if "tacked_acquired_date" in expected_lot:
            expected_tack = expected_lot["tacked_acquired_date"]
            if isinstance(expected_tack, str):
                expected_tack = _date.fromisoformat(expected_tack)
            assert match.tacked_acquired_date == expected_tack, (
                f"[{case['name']}] {expected_lot['ticker']} tacked_acquired_date: "
                f"ours={match.tacked_acquired_date}, expected={expected_tack}"
            )

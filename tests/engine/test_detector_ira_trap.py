"""IRC §1091 + Rev. Rul. 2008-5: IRA-trap wash sales.

When a loss is sold in a taxable account and substantially-identical stock is
bought in a tax-advantaged account (IRA, Roth, 401(k), HSA) within ±30 days,
§1091(a) disallows the loss, but §1091(d)'s basis rollover doesn't apply (no
IRA basis ledger). The result: a `kind="permanent_ira"` violation with no
basis adjustment and no holding-period tacking on the replacement lot.

A loss inside an IRA itself isn't a taxable event, so §1091 has nothing to
disallow — no violation should be emitted.
"""

from __future__ import annotations

from datetime import date

import pytest

from net_alpha.engine.detector import detect_wash_sales
from net_alpha.models.accounts import AccountType
from net_alpha.models.domain import Trade


def _sell(account: str, day: int, loss: float, qty: float = 10.0) -> Trade:
    proceeds = 1000.0
    return Trade(
        account=account,
        date=date(2024, 6, day),
        ticker="TSLA",
        action="Sell",
        quantity=qty,
        proceeds=proceeds,
        cost_basis=proceeds + loss,
    )


def _buy(account: str, day: int, qty: float = 10.0, basis: float = 1500.0) -> Trade:
    return Trade(
        account=account,
        date=date(2024, 6, day),
        ticker="TSLA",
        action="Buy",
        quantity=qty,
        cost_basis=basis,
    )


@pytest.mark.parametrize(
    "buy_account_type",
    [AccountType.ROTH_IRA, AccountType.TRAD_IRA, AccountType.K401, AccountType.HSA],
)
def test_taxable_loss_with_tax_advantaged_replacement_is_permanent_ira(buy_account_type):
    sell = _sell("schwab/taxable", 1, loss=500.0)
    buy = _buy("schwab/shelter", 5)
    account_types = {
        "schwab/taxable": AccountType.TAXABLE,
        "schwab/shelter": buy_account_type,
    }
    result = detect_wash_sales([sell, buy], etf_pairs={}, account_types=account_types)

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.kind == "permanent_ira"
    assert v.disallowed_loss == 500.0

    # Replacement lot basis MUST NOT be adjusted (§1091(d) can't apply).
    rep_lot = next(lot for lot in result.lots if lot.trade_id == buy.id)
    assert rep_lot.adjusted_basis == 1500.0
    # No §1223(4) tacking either — there's no rollover to tack onto.
    assert rep_lot.tacked_acquired_date is None


def test_taxable_to_taxable_unchanged_regression():
    """Same-taxable-account wash sale stays deferred and gets basis rollover + tacking."""
    sell = _sell("schwab/taxable", 1, loss=500.0)
    buy = _buy("schwab/taxable", 5)
    account_types = {"schwab/taxable": AccountType.TAXABLE}
    result = detect_wash_sales([sell, buy], etf_pairs={}, account_types=account_types)

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.kind == "deferred"
    assert v.disallowed_loss == 500.0

    rep_lot = next(lot for lot in result.lots if lot.trade_id == buy.id)
    assert rep_lot.adjusted_basis == 2000.0  # 1500 + 500 rollover


def test_loss_inside_ira_emits_no_violation():
    """A loss sale inside an IRA isn't a taxable event; nothing to disallow."""
    sell = _sell("schwab/roth", 1, loss=500.0)
    buy = _buy("schwab/taxable", 5)
    account_types = {
        "schwab/roth": AccountType.ROTH_IRA,
        "schwab/taxable": AccountType.TAXABLE,
    }
    result = detect_wash_sales([sell, buy], etf_pairs={}, account_types=account_types)

    assert result.violations == []


def test_missing_account_types_defaults_to_taxable():
    """When account_types is empty or missing keys, default to TAXABLE (current behavior)."""
    sell = _sell("schwab/taxable", 1, loss=500.0)
    buy = _buy("schwab/taxable", 5)
    result = detect_wash_sales([sell, buy], etf_pairs={}, account_types={})

    assert len(result.violations) == 1
    assert result.violations[0].kind == "deferred"


def test_no_account_types_arg_back_compat():
    """Existing callers that omit account_types must keep working (kind='deferred')."""
    sell = _sell("schwab/taxable", 1, loss=500.0)
    buy = _buy("schwab/taxable", 5)
    result = detect_wash_sales([sell, buy], etf_pairs={})

    assert len(result.violations) == 1
    assert result.violations[0].kind == "deferred"

"""Tests for forward-looking wash-sale + §1091 watch."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock as MM

from net_alpha.engine.washsale_watch import evaluate_target


def _make_target(symbol="SPY", broker="schwab", account="personal", target_shares=10):
    t = MM()
    t.id = 1
    t.symbol = symbol
    t.broker = broker
    t.account = account
    t.target_shares = target_shares
    t.target_dollars = None
    return t


def test_clean_when_no_recent_buys_or_loss():
    repo = MM()
    repo.latest_price.return_value = Decimal("400")
    repo.position_quantity.return_value = Decimal("10")  # already at target → no trade
    repo.average_basis.return_value = Decimal("390")
    repo.get_account_type.return_value = "taxable"
    repo.buys_in_window_non_taxable.return_value = []

    target = _make_target(target_shares=10)
    result = evaluate_target(target=target, repo=repo, today=date(2026, 5, 1))
    assert result.status == "clean"
    assert result.severity == "none"


def test_cannot_evaluate_when_no_quote():
    repo = MM()
    repo.latest_price.return_value = None
    target = _make_target()
    result = evaluate_target(target=target, repo=repo, today=date(2026, 5, 1))
    assert result.status == "cannot_evaluate"


def test_ira_trap_hard_when_exact_ticker_buy_in_ira_within_window():
    repo = MM()
    repo.latest_price.return_value = Decimal("100")
    repo.position_quantity.return_value = Decimal("10")  # holding 10
    repo.average_basis.return_value = Decimal("150")  # bought at 150 → loss at 100
    repo.get_account_type.return_value = "taxable"

    ira_buy = MM()
    ira_buy.id = 99
    ira_buy.ticker = "SPY"
    ira_buy.account = "schwab-roth"
    ira_buy.trade_date = "2026-04-15"
    repo.buys_in_window_non_taxable.return_value = [ira_buy]

    target = _make_target(target_shares=0)  # close to 0 = sell 10 → loss
    result = evaluate_target(target=target, repo=repo, today=date(2026, 5, 1))
    assert result.status == "ira_trap_risk"
    assert result.severity == "hard"
    assert 99 in (result.triggering_trade_ids or [])


def test_ira_trap_soft_when_etf_sibling_buy_in_ira():
    repo = MM()
    repo.latest_price.return_value = Decimal("400")
    repo.position_quantity.return_value = Decimal("10")
    repo.average_basis.return_value = Decimal("450")
    repo.get_account_type.return_value = "taxable"

    sibling_buy = MM()
    sibling_buy.id = 77
    sibling_buy.ticker = "VOO"  # ETF sibling of SPY
    sibling_buy.account = "schwab-ira"
    sibling_buy.trade_date = "2026-04-20"
    repo.buys_in_window_non_taxable.return_value = [sibling_buy]

    target = _make_target(symbol="SPY", target_shares=0)
    result = evaluate_target(target=target, repo=repo, today=date(2026, 5, 1))
    assert result.status == "ira_trap_risk"
    assert result.severity == "soft"

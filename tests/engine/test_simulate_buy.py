from datetime import date
from decimal import Decimal

from net_alpha.engine.simulator import simulate_buy
from net_alpha.models.domain import Account, Trade


def _sell(account, day, ticker, qty, proceeds, cost):
    return Trade(
        account=account,
        date=day,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost,
    )


P = Account(id=1, broker="schwab", label="personal")
R = Account(id=2, broker="schwab", label="roth")


def test_no_recent_losses_returns_clean_option_per_account():
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account=None,
        on_date=date(2025, 6, 1),
        accounts=[P, R],
        recent_trades=[],
        existing_violations=[],
        etf_pairs={},
    )
    assert {o.account.label for o in options} == {"personal", "roth"}
    for opt in options:
        assert opt.clean is True
        assert opt.matches == []
        assert opt.total_disallowed == Decimal("0")
        assert opt.proposed_basis == Decimal("1800")
        assert opt.adjusted_basis == Decimal("1800")


def test_unmatched_loss_within_window_creates_match():
    loss = _sell("schwab/personal", date(2025, 5, 20), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    assert len(options) == 1
    opt = options[0]
    assert opt.clean is False
    assert len(opt.matches) == 1
    m = opt.matches[0]
    assert m.matched_quantity == Decimal("10")
    # loss_amount = cost - proceeds = 2000 - 1500 = 500
    assert m.disallowed_loss == Decimal("500")
    assert m.confidence == "Confirmed"
    assert opt.proposed_basis == Decimal("1800")
    assert opt.adjusted_basis == Decimal("2300")  # 1800 + 500


def test_account_filter_returns_only_one_option():
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/roth",
        on_date=date(2025, 6, 1),
        accounts=[P, R],
        recent_trades=[],
        existing_violations=[],
        etf_pairs={},
    )
    assert len(options) == 1
    assert options[0].account.label == "roth"


def test_partial_qty_match_when_buy_qty_lt_loss_qty():
    loss = _sell("schwab/personal", date(2025, 5, 20), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("4"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    m = options[0].matches[0]
    assert m.matched_quantity == Decimal("4")
    # 500 disallowed * (4/10) = 200
    assert m.disallowed_loss == Decimal("200")
    assert options[0].adjusted_basis == Decimal("920")  # 720 + 200


def test_loss_already_wash_matched_is_skipped():
    from net_alpha.models.domain import WashSaleViolation

    loss = _sell("schwab/personal", date(2025, 5, 20), "TSLA", qty=10, proceeds=1500, cost=2000)
    existing = WashSaleViolation(
        loss_trade_id=loss.id,
        replacement_trade_id="some-other-buy",
        confidence="Confirmed",
        disallowed_loss=500.0,
        matched_quantity=10.0,
        ticker="TSLA",
        loss_account="schwab/personal",
        buy_account="schwab/personal",
        loss_sale_date=date(2025, 5, 20),
        triggering_buy_date=date(2025, 5, 25),
    )
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[existing],
        etf_pairs={},
    )
    assert options[0].clean is True


def test_gain_sale_in_window_is_not_a_match():
    gain = _sell("schwab/personal", date(2025, 5, 20), "TSLA", qty=10, proceeds=2500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[gain],
        existing_violations=[],
        etf_pairs={},
    )
    assert options[0].clean is True


def test_loss_in_other_account_still_matches_cross_account():
    loss = _sell("schwab/roth", date(2025, 5, 20), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    assert options[0].clean is False
    assert options[0].matches[0].loss_account == "schwab/roth"


def test_loss_on_day_zero_same_day_as_proposed_buy_matches():
    loss = _sell("schwab/personal", date(2025, 6, 1), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    assert options[0].clean is False


def test_loss_on_day_30_before_buy_still_matches():
    loss = _sell("schwab/personal", date(2025, 5, 2), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),  # exactly 30 days after
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    assert options[0].clean is False


def test_loss_on_day_31_before_buy_does_not_match():
    loss = _sell("schwab/personal", date(2025, 5, 1), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),  # 31 days after
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    assert options[0].clean is True


def test_loss_after_proposed_buy_does_not_match():
    """Future loss is simulate_sell's concern, not simulate_buy."""
    loss = _sell("schwab/personal", date(2025, 6, 5), "TSLA", qty=10, proceeds=1500, cost=2000)
    options = simulate_buy(
        ticker="TSLA",
        qty=Decimal("10"),
        price=Decimal("180"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={},
    )
    assert options[0].clean is True


def test_etf_substantially_identical_loss_matches_with_unclear_confidence():
    # Loss on SPY; proposed buy on VOO — bundled S&P 500 pair.
    loss = _sell("schwab/personal", date(2025, 5, 20), "SPY", qty=10, proceeds=4500, cost=5000)
    options = simulate_buy(
        ticker="VOO",
        qty=Decimal("10"),
        price=Decimal("450"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={"sp500": ["SPY", "VOO", "IVV", "SPLG"]},
    )
    assert options[0].clean is False
    assert len(options[0].matches) == 1
    m = options[0].matches[0]
    assert m.confidence == "Unclear"
    assert m.loss_ticker == "SPY"


def test_etf_unrelated_pair_does_not_match():
    # SPY (S&P 500) vs QQQ (Nasdaq-100) — not in same group.
    loss = _sell("schwab/personal", date(2025, 5, 20), "SPY", qty=10, proceeds=4500, cost=5000)
    options = simulate_buy(
        ticker="QQQ",
        qty=Decimal("10"),
        price=Decimal("400"),
        account="schwab/personal",
        on_date=date(2025, 6, 1),
        accounts=[P],
        recent_trades=[loss],
        existing_violations=[],
        etf_pairs={"sp500": ["SPY", "VOO"], "nasdaq": ["QQQ", "QQQM"]},
    )
    assert options[0].clean is True

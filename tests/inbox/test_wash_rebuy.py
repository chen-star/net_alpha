from datetime import date
from decimal import Decimal

from net_alpha.inbox.models import Severity, SignalType
from net_alpha.inbox.signals.wash_rebuy import compute_wash_rebuy
from tests.inbox.conftest import make_repo, make_violation


def test_day_30_after_loss_sale_excluded():
    today = date(2026, 5, 1)
    repo = make_repo(violations=[make_violation(loss_sale_date=date(2026, 4, 1))])
    # 30 days after 2026-04-01 is 2026-05-01 → still inside the 31-day window
    items = compute_wash_rebuy(repo=repo, today=today)
    assert items == []


def test_day_31_after_loss_sale_emitted():
    today = date(2026, 5, 2)  # 31 days after 2026-04-01
    repo = make_repo(violations=[make_violation(loss_sale_date=date(2026, 4, 1), disallowed_loss=612.0)])
    items = compute_wash_rebuy(repo=repo, today=today)
    assert len(items) == 1
    item = items[0]
    assert item.signal_type is SignalType.WASH_REBUY
    assert item.ticker == "AAPL"
    assert item.dismiss_key == "wash_rebuy:1"
    assert item.event_date == date(2026, 5, 2)
    assert item.days_until == 0
    assert item.severity is Severity.INFO
    assert item.dollar_impact == Decimal("612")
    assert item.deep_link == "/sim?action=buy&ticker=AAPL"
    assert "today" in item.subtitle.lower() or "0 day" in item.subtitle.lower()


def test_day_45_emitted_with_negative_days_until():
    today = date(2026, 5, 16)  # 45 days after 2026-04-01, safe_date was 2026-05-02
    repo = make_repo(violations=[make_violation(loss_sale_date=date(2026, 4, 1))])
    items = compute_wash_rebuy(repo=repo, today=today)
    assert len(items) == 1
    assert items[0].days_until == -14


def test_day_46_past_visible_window_excluded():
    today = date(2026, 5, 17)  # 46 days after; safe_date 14 days ago + 1
    repo = make_repo(violations=[make_violation(loss_sale_date=date(2026, 4, 1))])
    items = compute_wash_rebuy(repo=repo, today=today)
    assert items == []


def test_visible_days_override_respected():
    today = date(2026, 5, 17)  # 46d after — past default visible window
    repo = make_repo(violations=[make_violation(loss_sale_date=date(2026, 4, 1))])
    items = compute_wash_rebuy(repo=repo, today=today, visible_days=30)
    assert len(items) == 1


def test_multiple_violations_same_ticker_emit_separate_items():
    today = date(2026, 5, 5)
    repo = make_repo(
        violations=[
            make_violation(vid="1", loss_sale_date=date(2026, 4, 1), disallowed_loss=100),
            make_violation(vid="2", loss_sale_date=date(2026, 4, 3), disallowed_loss=200),
        ]
    )
    items = compute_wash_rebuy(repo=repo, today=today)
    assert {i.dismiss_key for i in items} == {"wash_rebuy:1", "wash_rebuy:2"}


def test_account_filter_excludes_other_accounts():
    today = date(2026, 5, 5)
    repo = make_repo(
        violations=[
            make_violation(vid="1", loss_sale_date=date(2026, 4, 1), loss_account="Schwab/A", buy_account="Schwab/A"),
            make_violation(vid="2", loss_sale_date=date(2026, 4, 1), loss_account="Schwab/B", buy_account="Schwab/B"),
        ]
    )
    items = compute_wash_rebuy(repo=repo, today=today, account="Schwab/A")
    assert {i.dismiss_key for i in items} == {"wash_rebuy:1"}


def test_account_filter_includes_cross_account_buys():
    """If filter matches the BUY side, the violation should still surface."""
    today = date(2026, 5, 5)
    repo = make_repo(
        violations=[
            make_violation(vid="1", loss_sale_date=date(2026, 4, 1), loss_account="Schwab/A", buy_account="Schwab/B"),
        ]
    )
    items = compute_wash_rebuy(repo=repo, today=today, account="Schwab/B")
    assert {i.dismiss_key for i in items} == {"wash_rebuy:1"}

from datetime import date
from decimal import Decimal

from net_alpha.portfolio.models import AccountValuePoint
from net_alpha.portfolio.account_value import build_eval_dates


def test_account_value_point_constructs_with_all_fields():
    p = AccountValuePoint(
        on=date(2025, 8, 14),
        contributions=Decimal("200000"),
        holdings_value=Decimal("180000"),
        cash_balance=Decimal("87432"),
        account_value=Decimal("267432"),
        net_pl=Decimal("67432"),
    )
    assert p.on == date(2025, 8, 14)
    assert p.account_value == Decimal("267432")
    assert p.net_pl == Decimal("67432")


def test_account_value_point_allows_none_for_unpriced_dates():
    p = AccountValuePoint(
        on=date(2025, 8, 14),
        contributions=Decimal("200000"),
        holdings_value=None,
        cash_balance=Decimal("87432"),
        account_value=None,
        net_pl=None,
    )
    assert p.holdings_value is None
    assert p.account_value is None
    assert p.net_pl is None


def test_eval_dates_year_period_weekly_plus_today():
    today = date(2025, 8, 14)
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=[])
    # First point is Jan 1, last is today; intermediate Fridays (weekly).
    assert dates[0] == date(2025, 1, 3)  # first Friday of 2025 is Jan 3
    assert dates[-1] == today
    # Roughly 32 Fridays Jan→mid-Aug + today
    assert 30 <= len(dates) <= 35
    # Strictly ascending, no duplicates
    assert dates == sorted(set(dates))


def test_eval_dates_event_dates_are_appended_and_deduped():
    today = date(2025, 8, 14)
    events = [date(2025, 3, 12), date(2025, 7, 4), date(2025, 1, 3)]  # last collides w/ Jan 3 Fri
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=events)
    assert date(2025, 3, 12) in dates
    assert date(2025, 7, 4) in dates
    assert dates.count(date(2025, 1, 3)) == 1  # deduped
    assert dates == sorted(set(dates))


def test_eval_dates_lifetime_uses_monthly_cadence():
    # Lifetime: period=None; first event date anchors the start.
    today = date(2025, 8, 14)
    events = [date(2022, 5, 10), date(2024, 1, 15), today]
    dates = build_eval_dates(period=None, today=today, event_dates=events)
    # ~ (2025-08 minus 2022-05) months ≈ 39 monthly points + 3 events + today
    assert dates[0] == date(2022, 5, 10)
    assert dates[-1] == today
    # Monthly: at least 30 anchor points, at most ~50
    assert 30 <= len(dates) <= 60


def test_eval_dates_year_in_progress_ends_at_today_not_dec_31():
    today = date(2025, 8, 14)
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=[])
    assert max(dates) == today
    assert date(2025, 12, 31) not in dates


def test_eval_dates_completed_year_ends_at_dec_31():
    today = date(2026, 5, 2)
    dates = build_eval_dates(period=(2025, 2026), today=today, event_dates=[])
    assert max(dates) == date(2025, 12, 31)

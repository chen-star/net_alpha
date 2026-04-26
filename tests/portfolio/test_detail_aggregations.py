from datetime import date
from decimal import Decimal

from net_alpha.models.domain import WashSaleViolation
from net_alpha.portfolio.detail_aggregations import (
    DetailSummary,
    compute_detail_summary,
    group_violations_by_ticker,
    lag_days,
    source_label,
)


def _v(**kw):
    defaults = dict(
        loss_trade_id="lt", replacement_trade_id="rt",
        confidence="Confirmed", disallowed_loss=100.0, matched_quantity=10.0,
        ticker="TSLA", loss_account="schwab/personal", buy_account="schwab/personal",
        loss_sale_date=date(2025, 6, 1), triggering_buy_date=date(2025, 6, 13),
        source="engine",
    )
    defaults.update(kw)
    return WashSaleViolation(**defaults)


def test_summary_zero_for_empty_list():
    s = compute_detail_summary([])
    assert s == DetailSummary(violation_count=0, disallowed_total=Decimal("0"),
                              confirmed_count=0, probable_count=0, unclear_count=0)


def test_summary_counts_confidence_and_sums():
    vs = [
        _v(confidence="Confirmed", disallowed_loss=200.0),
        _v(confidence="Probable", disallowed_loss=300.5),
        _v(confidence="Unclear", disallowed_loss=50.0),
    ]
    s = compute_detail_summary(vs)
    assert s.violation_count == 3
    assert s.disallowed_total == Decimal("550.50")
    assert s.confirmed_count == 1
    assert s.probable_count == 1
    assert s.unclear_count == 1


def test_group_by_ticker_sorts_by_disallowed_desc():
    vs = [
        _v(ticker="AAPL", disallowed_loss=100.0),
        _v(ticker="TSLA", disallowed_loss=500.0),
        _v(ticker="TSLA", disallowed_loss=200.0),
    ]
    groups = group_violations_by_ticker(vs)
    assert [g.ticker for g in groups] == ["TSLA", "AAPL"]
    assert groups[0].violation_count == 2
    assert groups[0].disallowed_total == Decimal("700")
    assert groups[1].violation_count == 1
    assert groups[1].disallowed_total == Decimal("100")


def test_lag_days_returns_int():
    v = _v(loss_sale_date=date(2025, 6, 1), triggering_buy_date=date(2025, 6, 13))
    assert lag_days(v) == 12


def test_lag_days_returns_none_when_dates_missing():
    v = _v(loss_sale_date=None)
    assert lag_days(v) is None


def test_source_label_schwab():
    v = _v(source="schwab_g_l")
    assert source_label(v) == "Schwab"


def test_source_label_cross_account():
    v = _v(source="engine", loss_account="schwab/personal", buy_account="schwab/roth")
    assert source_label(v) == "Cross-account"


def test_source_label_engine():
    v = _v(source="engine", loss_account="schwab/personal", buy_account="schwab/personal")
    assert source_label(v) == "Engine"

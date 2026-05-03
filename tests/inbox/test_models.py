from datetime import date
from decimal import Decimal

from net_alpha.inbox.models import InboxItem, Severity, SignalType


def test_inbox_item_minimal_construction():
    item = InboxItem(
        signal_type=SignalType.WASH_REBUY,
        dismiss_key="wash_rebuy:42",
        ticker="AAPL",
        title="AAPL safe to rebuy",
        subtitle="Wash window cleared yesterday",
        event_date=date(2026, 5, 1),
        days_until=-1,
        dollar_impact=Decimal("612"),
        severity=Severity.INFO,
        deep_link="/sim?action=buy&ticker=AAPL",
    )
    assert item.signal_type is SignalType.WASH_REBUY
    assert item.severity is Severity.INFO
    assert item.dollar_impact == Decimal("612")
    assert item.extras == {}


def test_inbox_item_dollar_impact_optional():
    item = InboxItem(
        signal_type=SignalType.LT_ELIGIBLE,
        dismiss_key="lt_eligible:7",
        ticker="GOOG",
        title="GOOG LT in 5d",
        subtitle="(no price)",
        event_date=date(2026, 5, 7),
        days_until=5,
        dollar_impact=None,
        severity=Severity.WATCH,
        deep_link="/ticker/GOOG?lot=7",
    )
    assert item.dollar_impact is None


def test_signal_type_values_are_stable_strings():
    assert SignalType.WASH_REBUY.value == "wash_rebuy"
    assert SignalType.LT_ELIGIBLE.value == "lt_eligible"
    assert SignalType.OPTION_EXPIRY.value == "option_expiry"
    assert SignalType.ASSIGNMENT_RISK.value == "assignment_risk"


def test_severity_values_are_stable_strings():
    assert Severity.INFO.value == "info"
    assert Severity.WATCH.value == "watch"
    assert Severity.URGENT.value == "urgent"

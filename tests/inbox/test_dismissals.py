from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlmodel import Session, create_engine

from net_alpha.inbox.dismissals import (
    apply_dismissals,
    is_dismissed,
    sweep_orphans,
    toggle_dismissal,
)
from net_alpha.inbox.models import InboxItem, Severity, SignalType


def _engine_with_table():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE dismissed_inbox_items (dismiss_key TEXT PRIMARY KEY, dismissed_at TEXT NOT NULL)"))
        s.commit()
    return engine


def _item(dismiss_key: str) -> InboxItem:
    return InboxItem(
        signal_type=SignalType.WASH_REBUY,
        dismiss_key=dismiss_key,
        ticker="AAPL",
        title="t",
        subtitle="s",
        event_date=date(2026, 5, 1),
        days_until=0,
        dollar_impact=Decimal("0"),
        severity=Severity.INFO,
        deep_link="/",
    )


def test_toggle_inserts_then_removes():
    engine = _engine_with_table()
    with Session(engine) as s:
        toggle_dismissal(s, "wash_rebuy:1")
        assert is_dismissed(s, "wash_rebuy:1") is True
        toggle_dismissal(s, "wash_rebuy:1")
        assert is_dismissed(s, "wash_rebuy:1") is False


def test_apply_dismissals_filters_items():
    engine = _engine_with_table()
    with Session(engine) as s:
        toggle_dismissal(s, "wash_rebuy:1")
        items = [_item("wash_rebuy:1"), _item("wash_rebuy:2")]
        out = apply_dismissals(s, items)
        keys = [i.dismiss_key for i in out]
        assert keys == ["wash_rebuy:2"]


def test_sweep_orphans_removes_dismissals_not_in_live_set():
    engine = _engine_with_table()
    with Session(engine) as s:
        toggle_dismissal(s, "wash_rebuy:1")  # live
        toggle_dismissal(s, "wash_rebuy:99")  # orphan
        sweep_orphans(s, live_keys={"wash_rebuy:1"})
        assert is_dismissed(s, "wash_rebuy:1") is True
        assert is_dismissed(s, "wash_rebuy:99") is False


def test_sweep_orphans_with_empty_live_set_clears_table():
    engine = _engine_with_table()
    with Session(engine) as s:
        toggle_dismissal(s, "wash_rebuy:1")
        sweep_orphans(s, live_keys=set())
        assert is_dismissed(s, "wash_rebuy:1") is False

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlmodel import Session, create_engine

from net_alpha.inbox.aggregator import gather_inbox
from net_alpha.inbox.config import InboxConfig
from net_alpha.inbox.dismissals import toggle_dismissal
from net_alpha.inbox.models import Severity, SignalType
from net_alpha.models.domain import OptionDetails
from tests.inbox.conftest import (
    make_lot,
    make_prices_stub,
    make_repo,
    make_violation,
)


def _engine_with_table():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as s:
        s.exec(text("CREATE TABLE dismissed_inbox_items (dismiss_key TEXT PRIMARY KEY, dismissed_at TEXT NOT NULL)"))
        s.commit()
    return engine


def test_aggregator_combines_signals_and_sorts():
    today = date(2026, 5, 1)
    repo = make_repo(
        violations=[make_violation(vid="1", loss_sale_date=date(2026, 4, 1))],  # safe today (INFO)
        lots=[
            make_lot(
                lid="42", ticker="AAPL", acquired=today - timedelta(days=350), quantity=10, cost_basis=1000
            ),  # LT in 16 days, gain → INFO
            make_lot(
                lid="9",
                trade_id="t-9",
                ticker="GOOG",
                acquired=today - timedelta(days=100),
                quantity=-1,
                cost_basis=100,
                option=OptionDetails(strike=200, expiry=today, call_put="C"),
            ),
            # short call, ITM, expires today → URGENT expiry + URGENT assignment risk
        ],
    )
    prices = make_prices_stub({"AAPL": Decimal("150"), "GOOG": Decimal("210")})
    engine = _engine_with_table()
    with Session(engine) as s:
        items = gather_inbox(
            repo=repo,
            prices=prices,
            session=s,
            today=today,
            config=InboxConfig(),
            st_rate=Decimal("0.37"),
            lt_rate=Decimal("0.20"),
        )
    # All items present, URGENT first
    severities = [i.severity for i in items]
    assert severities[0] is Severity.URGENT
    assert Severity.INFO in severities


def test_dismissed_items_are_filtered():
    today = date(2026, 5, 2)
    repo = make_repo(violations=[make_violation(vid="1", loss_sale_date=date(2026, 4, 1))])
    prices = make_prices_stub({})
    engine = _engine_with_table()
    with Session(engine) as s:
        toggle_dismissal(s, "wash_rebuy:1")
        items = gather_inbox(
            repo=repo,
            prices=prices,
            session=s,
            today=today,
            config=InboxConfig(),
            st_rate=Decimal("0.37"),
            lt_rate=Decimal("0.20"),
        )
    assert items == []


def test_orphan_dismissal_is_swept():
    """A dismissal whose key has no live signal must be deleted."""
    today = date(2026, 5, 2)
    repo = make_repo()  # no signals at all
    prices = make_prices_stub({})
    engine = _engine_with_table()
    with Session(engine) as s:
        toggle_dismissal(s, "wash_rebuy:999")  # orphan
        gather_inbox(
            repo=repo,
            prices=prices,
            session=s,
            today=today,
            config=InboxConfig(),
            st_rate=Decimal("0.37"),
            lt_rate=Decimal("0.20"),
        )
        rows = s.exec(text("SELECT dismiss_key FROM dismissed_inbox_items")).all()
        assert rows == []


def test_sort_by_severity_then_days_then_dollars():
    """When multiple items share severity, |days_until| asc; then |dollar_impact| desc."""
    today = date(2026, 5, 1)
    # Two LT items with the same severity (INFO; > 14 days):
    repo = make_repo(
        lots=[
            make_lot(lid="A", ticker="LO_DOLLAR", acquired=today - timedelta(days=345), quantity=1, cost_basis=10),
            make_lot(lid="B", ticker="HI_DOLLAR", acquired=today - timedelta(days=345), quantity=10, cost_basis=10),
        ]
    )
    prices = make_prices_stub({"LO_DOLLAR": Decimal("11"), "HI_DOLLAR": Decimal("100")})
    engine = _engine_with_table()
    with Session(engine) as s:
        items = gather_inbox(
            repo=repo,
            prices=prices,
            session=s,
            today=today,
            config=InboxConfig(),
            st_rate=Decimal("0.37"),
            lt_rate=Decimal("0.20"),
        )
    info = [i for i in items if i.signal_type is SignalType.LT_ELIGIBLE]
    # Both have days_until = 21; HI_DOLLAR has bigger dollar_impact → first
    assert info[0].ticker == "HI_DOLLAR"
    assert info[1].ticker == "LO_DOLLAR"


def test_account_filter_passes_through():
    today = date(2026, 5, 2)
    repo = make_repo(
        violations=[
            make_violation(vid="1", loss_sale_date=date(2026, 4, 1), loss_account="Schwab/A", buy_account="Schwab/A"),
            make_violation(vid="2", loss_sale_date=date(2026, 4, 1), loss_account="Schwab/B", buy_account="Schwab/B"),
        ]
    )
    prices = make_prices_stub({})
    engine = _engine_with_table()
    with Session(engine) as s:
        items = gather_inbox(
            repo=repo,
            prices=prices,
            session=s,
            today=today,
            config=InboxConfig(),
            st_rate=Decimal("0.37"),
            lt_rate=Decimal("0.20"),
            account="Schwab/A",
        )
    assert {i.dismiss_key for i in items} == {"wash_rebuy:1"}

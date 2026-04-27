from datetime import date

from net_alpha.models.domain import CashEvent


def test_cash_event_natural_key_is_deterministic():
    e1 = CashEvent(
        account="Schwab/short_term",
        event_date=date(2026, 3, 31),
        kind="dividend",
        amount=4.47,
        ticker="SQQQ",
        description="PROSHARES ULTRAPRO SHORTQQQ",
    )
    e2 = CashEvent(
        account="Schwab/short_term",
        event_date=date(2026, 3, 31),
        kind="dividend",
        amount=4.47,
        ticker="SQQQ",
        description="PROSHARES ULTRAPRO SHORTQQQ",
    )
    assert e1.compute_natural_key() == e2.compute_natural_key()


def test_cash_event_natural_key_differs_on_kind():
    base = dict(
        account="Schwab/short_term",
        event_date=date(2026, 3, 31),
        amount=100.0,
        ticker=None,
        description="Tfr WELLS FARGO BANK",
    )
    a = CashEvent(kind="transfer_in", **base).compute_natural_key()
    b = CashEvent(kind="transfer_out", **base).compute_natural_key()
    assert a != b


def test_cash_event_amount_is_always_positive():
    # Sign comes from kind, not amount. amount is always positive in the model.
    e = CashEvent(
        account="Schwab/short_term",
        event_date=date(2026, 3, 31),
        kind="transfer_in",
        amount=600.0,
        ticker=None,
        description="Tfr WELLS FARGO BANK",
    )
    assert e.amount > 0

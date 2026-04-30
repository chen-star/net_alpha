"""Tests for sim_suggestions.top_suggestions chip picker."""

from datetime import date
from decimal import Decimal

from net_alpha.portfolio.sim_suggestions import (
    LossClose,
    Position,
    SimSuggestion,  # noqa: F401
    top_suggestions,
)


def _pos(symbol, qty, basis_per_share, last_price, account="schwab/personal"):
    return Position(
        symbol=symbol,
        account_label=account,
        qty=Decimal(str(qty)),
        cost_basis=Decimal(str(qty)) * Decimal(str(basis_per_share)),
        last_price=Decimal(str(last_price)),
    )


def test_returns_three_chips_when_data_supports_it():
    positions = [
        _pos("LOSS", 10, 100, 80),
        _pos("GAIN", 5, 50, 90),
    ]
    losses = [
        LossClose(
            symbol="WASH",
            account_label="schwab/personal",
            closed_on=date(2026, 4, 20),
            loss=Decimal("-200"),
            lockout_clear=date(2026, 5, 20),
            last_price=Decimal("75"),
        ),
    ]
    chips = top_suggestions(positions, losses, today=date(2026, 4, 29))
    kinds = {c.kind for c in chips}
    assert kinds == {"largest_loss", "wash_risk", "largest_gain"}


def test_empty_portfolio_yields_demo_chip():
    chips = top_suggestions([], [], today=date(2026, 4, 29))
    assert len(chips) == 1
    assert chips[0].kind == "demo"


def test_largest_loss_picked_correctly():
    positions = [
        _pos("SMALL_LOSS", 5, 100, 95),  # -25
        _pos("BIG_LOSS", 10, 100, 80),  # -200
    ]
    chips = top_suggestions(positions, [], today=date(2026, 4, 29))
    losers = [c for c in chips if c.kind == "largest_loss"]
    assert losers and losers[0].ticker == "BIG_LOSS"


def test_no_losses_means_no_loss_chip():
    chips = top_suggestions([_pos("GAIN", 5, 50, 90)], [], today=date(2026, 4, 29))
    assert all(c.kind != "largest_loss" for c in chips)


def test_no_gains_means_no_gain_chip():
    chips = top_suggestions([_pos("LOSS", 5, 100, 80)], [], today=date(2026, 4, 29))
    assert all(c.kind != "largest_gain" for c in chips)


def test_wash_risk_only_when_unexpired():
    losses_expired = [
        LossClose(
            symbol="OLD",
            account_label="schwab/personal",
            closed_on=date(2026, 1, 1),
            loss=Decimal("-100"),
            lockout_clear=date(2026, 1, 31),
            last_price=Decimal("50"),
        ),
    ]
    chips = top_suggestions([_pos("LOSS", 5, 100, 80)], losses_expired, today=date(2026, 4, 29))
    assert all(c.kind != "wash_risk" for c in chips)


def test_wash_risk_picks_most_recent():
    older = LossClose(
        symbol="OLD",
        account_label="schwab/personal",
        closed_on=date(2026, 4, 10),
        loss=Decimal("-50"),
        lockout_clear=date(2026, 5, 10),
        last_price=Decimal("60"),
    )
    newer = LossClose(
        symbol="NEW",
        account_label="schwab/personal",
        closed_on=date(2026, 4, 25),
        loss=Decimal("-50"),
        lockout_clear=date(2026, 5, 25),
        last_price=Decimal("70"),
    )
    chips = top_suggestions([], [older, newer], today=date(2026, 4, 29))
    wash_chips = [c for c in chips if c.kind == "wash_risk"]
    assert wash_chips and wash_chips[0].ticker == "NEW"

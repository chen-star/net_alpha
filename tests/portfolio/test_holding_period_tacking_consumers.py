"""Other LT/ST consumers honor §1223(4) tacking.

Beyond the lot_selector and ST/LT classifier, several portfolio modules
compute days-held from a raw lot date. They must use the effective acquired
date (which respects wash-sale tacking) so tacked lots aren't mislabeled.
"""

from __future__ import annotations

from datetime import date, timedelta

from net_alpha.models.domain import Lot
from net_alpha.portfolio.lot_aging import top_lots_crossing_ltcg


def _lot(*, acquired: date, tacked: date | None, qty: float = 10.0):
    return Lot(
        id=f"lot-{acquired.isoformat()}",
        trade_id="t1",
        ticker="SPY",
        date=acquired,
        quantity=qty,
        cost_basis=1000.0,
        adjusted_basis=1000.0,
        account="default",
        tacked_acquired_date=tacked,
    )


def test_top_lots_crossing_ltcg_skips_already_lt_via_tacking(monkeypatch):
    """A 100-day raw hold that tacked >365 days back is already LT — never appears."""
    today = date(2026, 5, 1)

    class FakeDate(date):
        @classmethod
        def today(cls):  # noqa: D401
            return today

    import net_alpha.portfolio.lot_aging as la

    monkeypatch.setattr(la.dt, "date", FakeDate)

    tacked_lot = _lot(acquired=today - timedelta(days=100), tacked=today - timedelta(days=500))
    untacked_lot = _lot(acquired=today - timedelta(days=300), tacked=None)

    rows = top_lots_crossing_ltcg(lots=[tacked_lot, untacked_lot], horizon_days=90)
    # tacked_lot is already long-term (raw 100 days but tacked 500 ago → LTCG date passed
    # 135 days ago). Only the untacked one (65 days to LTCG) appears.
    assert len(rows) == 1
    assert rows[0].days_to_ltcg == 65


def test_top_lots_crossing_ltcg_uses_effective_for_window(monkeypatch):
    """A lot whose tacked date puts LTCG inside the horizon must appear with the
    correctly computed days_to_ltcg (from effective_acquired_date)."""
    today = date(2026, 5, 1)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return today

    import net_alpha.portfolio.lot_aging as la

    monkeypatch.setattr(la.dt, "date", FakeDate)

    # Raw acquired 10 days ago, tacked back 350 days → effective LTCG date is 15 days away.
    lot = _lot(acquired=today - timedelta(days=10), tacked=today - timedelta(days=350))
    rows = top_lots_crossing_ltcg(lots=[lot], horizon_days=90)
    assert len(rows) == 1
    assert rows[0].days_to_ltcg == 15

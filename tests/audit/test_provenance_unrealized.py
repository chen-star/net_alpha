from datetime import date

from net_alpha.audit.provenance import UnrealizedPLRef, provenance_for
from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import Trade
from tests.audit.conftest import seed_import


def test_unrealized_provenance_lists_open_lot_buys(repo, schwab_account):
    # Two buys for AAPL — both should remain open lots.
    trades = [
        Trade(account="Schwab/Tax", date=date(2026, 1, 15), ticker="AAPL",
              action="Buy", quantity=10, cost_basis=1000.0),
        Trade(account="Schwab/Tax", date=date(2026, 2, 1), ticker="AAPL",
              action="Buy", quantity=5, cost_basis=520.0),
    ]
    seed_import(repo, schwab_account, trades)

    # Populate the lots table via detect_in_window + replace_lots_in_window.
    win_start = date(2026, 1, 1)
    win_end = date(2026, 3, 1)
    result = detect_in_window(
        repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={}
    )
    repo.replace_lots_in_window(win_start, win_end, result.lots)

    ref = UnrealizedPLRef(kind="unrealized_pl", account_id=schwab_account.id, symbol="AAPL")
    trace = provenance_for(ref, repo)

    # Two contributing buys.
    assert len(trace.trades) == 2
    assert all(t.action == "Buy" for t in trace.trades)
    assert all(t.symbol == "AAPL" for t in trace.trades)
    # Total = -(adjusted_basis sum). With no wash-sale adjustments,
    # adjusted_basis == cost_basis, so total = -(1000 + 520) = -1520.
    assert trace.total == -1520.0

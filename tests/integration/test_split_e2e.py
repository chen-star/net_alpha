"""End-to-end: import -> sync_splits -> verify lot adjusted -> imports rm
-> re-import -> verify lot still split-adjusted on the way back through
recompute."""

from datetime import date
from unittest.mock import patch

from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.pricing.provider import SplitEvent


def test_split_survives_unimport_reimport_cycle(builders, repo, client):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "SQQQ", date(2024, 1, 5), qty=100, cost=2000),
        ],
        csv_filename="initial.csv",
    )
    recompute_all_violations(repo, load_etf_pairs())

    with patch(
        "net_alpha.pricing.yahoo.YahooPriceProvider.fetch_splits",
        return_value=[SplitEvent(symbol="SQQQ", split_date=date(2025, 1, 13), ratio=0.1)],
    ):
        client.post("/splits/sync?symbols=SQQQ")

    lots = repo.get_lots_for_ticker("SQQQ")
    assert lots[0].quantity == 10.0  # 100 * 0.1

    # Unimport.
    imports = repo.list_imports()
    repo.remove_import(imports[0].id)

    # Re-import the same trade.
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "SQQQ", date(2024, 1, 5), qty=100, cost=2000),
        ],
        csv_filename="reimport.csv",
    )
    recompute_all_violations(repo, load_etf_pairs())

    # Lot should still be split-adjusted (split is in the splits table; recompute
    # calls apply_splits at the end).
    lots = repo.get_lots_for_ticker("SQQQ")
    assert lots[0].quantity == 10.0

"""When a CSV brings in a NEW symbol (not previously seen in any import),
the import flow should auto-call sync_splits for that symbol so existing
splits are applied immediately. Existing symbols should NOT trigger
auto-fetch (avoids burning network on every re-import)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch


def test_first_import_triggers_split_autosync(builders, repo):
    """A brand-new symbol triggers fetch_splits during import."""
    fetch_calls = []

    def fake_fetch(self, symbol):
        fetch_calls.append(symbol)
        return []

    with patch("net_alpha.pricing.yahoo.YahooPriceProvider.fetch_splits", fake_fetch):
        builders.seed_import(
            repo,
            "schwab",
            "lt",
            [
                builders.make_buy("schwab/lt", "NEWSYM", date(2026, 1, 5)),
            ],
            csv_filename="first.csv",
        )
        # seed_import bypasses the route's auto-sync hook.
        # Call the helper directly to verify its behavior in isolation.
        from net_alpha.splits.sync import _post_import_autosync_splits

        _post_import_autosync_splits(repo, new_symbols={"NEWSYM"}, existing_symbols=set())

    assert "NEWSYM" in fetch_calls


def test_reimport_of_existing_symbol_skips_autosync(builders, repo):
    fetch_calls = []

    def fake_fetch(self, symbol):
        fetch_calls.append(symbol)
        return []

    with patch("net_alpha.pricing.yahoo.YahooPriceProvider.fetch_splits", fake_fetch):
        from net_alpha.splits.sync import _post_import_autosync_splits

        _post_import_autosync_splits(repo, new_symbols={"AAPL"}, existing_symbols={"AAPL"})

    assert fetch_calls == []

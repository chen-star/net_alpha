"""apply_splits is the post-recompute step that mutates regenerated lots
to reflect known stock splits. It's idempotent (lot_overrides serves as
the de-dup key) and a no-op on lots dated >= the split's ex-date."""

from datetime import date

from net_alpha.splits.apply import apply_splits


def test_forward_2_for_1_doubles_qty_preserves_basis(repo, builders):
    """A 2-for-1 split on a 10-share, $1500 lot bought before the ex-date should
    yield 20 shares with $1500 unchanged total adjusted_basis."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2020, 8, 1), qty=10, cost=1500),
        ],
    )
    repo.add_split("AAPL", date(2020, 8, 31), 2.0, "yahoo")

    # Trigger initial wash-sale recompute so lots exist.
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    apply_splits(repo)

    lots = repo.get_lots_for_ticker("AAPL")
    assert len(lots) == 1
    assert lots[0].quantity == 20.0
    assert lots[0].adjusted_basis == 1500.0


def test_reverse_1_for_10_shrinks_qty(repo, builders):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "SQQQ", date(2024, 1, 5), qty=100, cost=2000),
        ],
    )
    repo.add_split("SQQQ", date(2025, 1, 13), 0.1, "yahoo")

    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    apply_splits(repo)

    lots = repo.get_lots_for_ticker("SQQQ")
    assert len(lots) == 1
    assert lots[0].quantity == 10.0
    assert lots[0].adjusted_basis == 2000.0


def test_lot_dated_after_split_is_untouched(repo, builders):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2021, 1, 5), qty=10, cost=1500),
        ],
    )
    repo.add_split("AAPL", date(2020, 8, 31), 2.0, "yahoo")  # ex-date BEFORE the buy

    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    apply_splits(repo)

    lots = repo.get_lots_for_ticker("AAPL")
    assert len(lots) == 1
    assert lots[0].quantity == 10.0  # unchanged


def test_other_symbol_lots_untouched(repo, builders):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2020, 1, 1), qty=10, cost=1500),
            builders.make_buy("schwab/lt", "NVDA", date(2020, 1, 1), qty=10, cost=2000),
        ],
    )
    repo.add_split("AAPL", date(2020, 8, 31), 2.0, "yahoo")

    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    apply_splits(repo)

    nvda_lots = repo.get_lots_for_ticker("NVDA")
    assert nvda_lots[0].quantity == 10.0


def test_apply_splits_is_idempotent(repo, builders):
    """Calling apply_splits twice produces the same result. lot_overrides is
    written exactly once per (split, trade) pair."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2020, 1, 1), qty=10, cost=1500),
        ],
    )
    repo.add_split("AAPL", date(2020, 8, 31), 2.0, "yahoo")

    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    apply_splits(repo)
    apply_splits(repo)  # second call should be a no-op

    lots = repo.get_lots_for_ticker("AAPL")
    assert lots[0].quantity == 20.0  # not 40
    trade_id = int(repo.get_trades_for_ticker("AAPL")[0].id)
    overrides = repo.get_lot_overrides_for_trade(trade_id)
    # Exactly one quantity override row written for the split.
    qty_overrides = [o for o in overrides if o.field == "quantity" and o.reason == "split"]
    assert len(qty_overrides) == 1


def test_apply_manual_overrides_replays_latest_edit(repo, builders):
    from datetime import date

    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1500),
    ])
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations
    recompute_all_violations(repo, load_etf_pairs())

    trade_id = int(repo.get_trades_for_ticker("AAPL")[0].id)
    repo.add_lot_override(
        trade_id=trade_id, field="quantity",
        old_value=10.0, new_value=2.0, reason="manual",
    )

    # A subsequent recompute would otherwise blow away the qty=2 edit; the
    # apply_manual_overrides call inside recompute_all_violations should
    # re-apply it.
    recompute_all_violations(repo, load_etf_pairs())

    lots = repo.get_lots_for_ticker("AAPL")
    assert lots[0].quantity == 2.0


def test_apply_manual_overrides_latest_edit_wins(repo, builders):
    """When two manual overrides exist for the same (trade_id, field),
    apply_manual_overrides applies the LATEST one (by edited_at)."""
    import time
    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1500),
    ])
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    recompute_all_violations(repo, load_etf_pairs())

    trade_id = int(repo.get_trades_for_ticker("AAPL")[0].id)
    repo.add_lot_override(
        trade_id=trade_id, field="quantity",
        old_value=10.0, new_value=2.0, reason="manual",
    )
    # Sleep briefly so the second override's edited_at is strictly later.
    time.sleep(0.01)
    repo.add_lot_override(
        trade_id=trade_id, field="quantity",
        old_value=2.0, new_value=5.0, reason="manual",
    )

    recompute_all_violations(repo, load_etf_pairs())

    lots = repo.get_lots_for_ticker("AAPL")
    assert lots[0].quantity == 5.0  # latest, not 2.0 (first) and not 10.0 (raw)


def test_apply_splits_handles_multiple_consecutive_splits(repo, builders):
    """Two splits on the same symbol stack multiplicatively. AAPL did this:
    7-for-1 on 2014-06-09, then 4-for-1 on 2020-08-31. A 1-share buy in 2010
    should become 1 * 7 * 4 = 28 shares after both are applied."""
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2010, 1, 4), qty=1, cost=200),
        ],
    )
    repo.add_split("AAPL", date(2014, 6, 9), 7.0, "yahoo")
    repo.add_split("AAPL", date(2020, 8, 31), 4.0, "yahoo")

    recompute_all_violations(repo, load_etf_pairs())

    apply_splits(repo)

    lots = repo.get_lots_for_ticker("AAPL")
    assert len(lots) == 1
    assert lots[0].quantity == 28.0
    assert lots[0].adjusted_basis == 200.0  # basis preserved across both splits

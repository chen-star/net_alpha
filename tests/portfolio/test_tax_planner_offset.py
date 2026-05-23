from datetime import date
from decimal import Decimal

from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.portfolio.tax_planner import OffsetBudget, PlannedTrade, compute_offset_budget


def test_offset_budget_constructs() -> None:
    b = OffsetBudget(
        year=2026,
        realized_losses_ytd=Decimal("-1000"),
        realized_gains_ytd=Decimal("500"),
        net_realized=Decimal("-500"),
        used_against_ordinary=Decimal("500"),
        carryforward_projection=Decimal("0"),
        planned_delta=Decimal("0"),
    )
    assert b.cap_against_ordinary == Decimal("3000")  # default


def test_planned_trade_constructs() -> None:
    pt = PlannedTrade(
        symbol="UUUU",
        account_id=1,
        action="Sell",
        qty=Decimal("100"),
        price=Decimal("4"),
        on=date(2026, 6, 1),
    )
    assert pt.action == "Sell"


def test_compute_offset_budget_no_trades(repo) -> None:
    b = compute_offset_budget(repo=repo, year=2026)
    assert b.realized_losses_ytd == Decimal("0")
    assert b.realized_gains_ytd == Decimal("0")
    assert b.net_realized == Decimal("0")
    assert b.used_against_ordinary == Decimal("0")
    assert b.carryforward_projection == Decimal("0")


def test_compute_offset_budget_aggregates_realized_in_year(
    repo,
    schwab_account,
    seed_import,
) -> None:
    buys = [
        Trade(
            account=schwab_account.display(),
            date=date(2026, 1, 5),
            ticker="UUUU",
            action="Buy",
            quantity=Decimal("1"),
            proceeds=Decimal("0"),
            cost_basis=Decimal("100"),
        ),
        Trade(
            account=schwab_account.display(),
            date=date(2026, 1, 5),
            ticker="AAPL",
            action="Buy",
            quantity=Decimal("1"),
            proceeds=Decimal("0"),
            cost_basis=Decimal("100"),
        ),
    ]
    sells = [
        Trade(
            account=schwab_account.display(),
            date=date(2026, 3, 1),
            ticker="UUUU",
            action="Sell",
            quantity=Decimal("1"),
            proceeds=Decimal("80"),
            cost_basis=Decimal("100"),
        ),
        Trade(
            account=schwab_account.display(),
            date=date(2026, 4, 1),
            ticker="AAPL",
            action="Sell",
            quantity=Decimal("1"),
            proceeds=Decimal("130"),
            cost_basis=Decimal("100"),
        ),
    ]
    seed_import(repo, schwab_account, buys + sells)
    b = compute_offset_budget(repo=repo, year=2026)
    assert b.realized_losses_ytd == Decimal("-20")
    assert b.realized_gains_ytd == Decimal("30")
    assert b.net_realized == Decimal("10")
    assert b.used_against_ordinary == Decimal("0")


def test_compute_offset_budget_clamps_loss_at_3000_cap(
    repo,
    schwab_account,
    seed_import,
) -> None:
    buy = Trade(
        account=schwab_account.display(),
        date=date(2026, 1, 5),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("10000"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=date(2026, 3, 1),
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("100"),
        proceeds=Decimal("5000"),
        cost_basis=Decimal("10000"),
    )
    seed_import(repo, schwab_account, [buy, sell])
    b = compute_offset_budget(repo=repo, year=2026)
    assert b.realized_losses_ytd == Decimal("-5000")
    assert b.used_against_ordinary == Decimal("3000")
    assert b.carryforward_projection == Decimal("2000")


def test_compute_offset_budget_planned_trades_shift_delta(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    buy = Trade(
        account=schwab_account.display(),
        date=date(2026, 1, 5),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    seed_import(repo, schwab_account, [buy])
    seed_lots(repo)
    planned = [
        PlannedTrade(
            symbol="UUUU",
            account_id=schwab_account.id or 0,
            action="Sell",
            qty=Decimal("100"),
            price=Decimal("8"),
            on=date(2026, 6, 1),
        )
    ]
    b = compute_offset_budget(repo=repo, year=2026, planned_trades=planned)
    # Planned: sell 100 at 8 vs basis 10/sh = -200 realized.
    assert b.planned_delta == Decimal("-200")


def test_offset_budget_includes_incoming_carryforward(repo) -> None:
    """A $4,000 ST carryforward INTO 2025 means the user already has $4K of
    headroom against current-year gains before any new losses are needed."""
    from net_alpha.portfolio.carryforward import Carryforward

    cf = Carryforward(st=Decimal("4000"), lt=Decimal("0"), source="user")
    budget = compute_offset_budget(repo=repo, year=2025, carryforward=cf)
    assert budget.incoming_carryforward_st == Decimal("4000")
    assert budget.incoming_carryforward_lt == Decimal("0")


def test_offset_budget_no_carryforward_arg_defaults_to_zero(repo) -> None:
    """When carryforward arg omitted (or None), incoming fields are 0."""
    budget = compute_offset_budget(repo=repo, year=2025)
    assert budget.incoming_carryforward_st == Decimal("0")
    assert budget.incoming_carryforward_lt == Decimal("0")


def test_offset_budget_lt_carryforward_absorbs_st_gain_no_ordinary_used(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """§1212(b)(1)(B): a $4K LT capital-loss carryforward netting against a
    $5K ST gain leaves $1K ST gain — no net loss, no §1211(b) cap consumed,
    no CF rolls forward.

    Old buggy behavior would lump cf_total + |net| together, treat the $4K
    LT CF as an unused loss, and clamp it at the $3K cap — showing $3K
    "used against ordinary" the user never actually realized.
    """
    from net_alpha.portfolio.carryforward import Carryforward

    buy = Trade(
        account=schwab_account.display(),
        date=date(2026, 1, 5),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=date(2026, 3, 1),
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("100"),
        proceeds=Decimal("6000"),
        cost_basis=Decimal("1000"),
    )
    seed_import(repo, schwab_account, [buy, sell])

    cf = Carryforward(st=Decimal("0"), lt=Decimal("4000"), source="user")
    budget = compute_offset_budget(repo=repo, year=2026, carryforward=cf)
    # $5K ST gain absorbed by $4K LT CF (§1212(b)(1)(B) cross-bucket).
    # Net: $1K ST gain. No deduction against ordinary; no CF rolls forward.
    assert budget.used_against_ordinary == Decimal("0")
    assert budget.carryforward_projection == Decimal("0")


def test_offset_budget_excludes_tax_advantaged_account_losses(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """Losses inside an IRA / Roth / 401(k) / HSA are NOT realized for tax —
    they must not show up in the offset budget. §1211(b) headroom is a
    taxable-account concept.
    """
    # Set up a taxable schwab account (default) with no activity, plus an
    # IRA-typed account with a $1,000 "loss" that doesn't count for taxes.
    ira_acct = repo.get_or_create_account(broker="schwab", label="IRA")
    repo.set_account_type(broker="schwab", label="IRA", type_="trad_ira")

    buy = Trade(
        account=ira_acct.display(),
        date=date(2026, 1, 5),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("5000"),
    )
    sell = Trade(
        account=ira_acct.display(),
        date=date(2026, 3, 1),
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("100"),
        proceeds=Decimal("4000"),
        cost_basis=Decimal("5000"),
    )
    seed_import(repo, ira_acct, [buy, sell])

    b = compute_offset_budget(repo=repo, year=2026)
    # IRA losses are not tax-realized — budget should be flat.
    assert b.realized_losses_ytd == Decimal("0")
    assert b.realized_gains_ytd == Decimal("0")
    assert b.net_realized == Decimal("0")
    assert b.used_against_ordinary == Decimal("0")


def test_offset_budget_carryforward_inflates_used_against_ordinary(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """If incoming cf is $4K and current-year net loss is $2K, used_against_ordinary
    should reflect the combined $6K loss, capped at $3K against ordinary;
    carryforward_projection $3K residue."""
    from net_alpha.portfolio.carryforward import Carryforward

    # Pre-seed repo with a $2K realized loss in 2025.
    buy = Trade(
        account=schwab_account.display(),
        date=date(2025, 1, 5),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("5000"),
    )
    sell = Trade(
        account=schwab_account.display(),
        date=date(2025, 3, 1),
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("100"),
        proceeds=Decimal("3000"),
        cost_basis=Decimal("5000"),
    )
    seed_import(repo, schwab_account, [buy, sell])

    cf = Carryforward(st=Decimal("4000"), lt=Decimal("0"), source="user")
    budget = compute_offset_budget(repo=repo, year=2025, carryforward=cf)
    assert budget.realized_losses_ytd == Decimal("-2000")
    assert budget.used_against_ordinary == Decimal("3000")
    # carryforward_projection is the residue: $4K cf + $2K loss - $3K cap = $3K
    assert budget.carryforward_projection == Decimal("3000")


def test_offset_budget_losses_plus_gains_match_st_plus_lt(
    repo,
    schwab_account,
    seed_import,
    seed_lots,
) -> None:
    """Audit #4: ``realized_losses_ytd + realized_gains_ytd`` must equal the
    net P&L surfaced as ST/LT (``realized_pnl_split_by_year``). Pre-fix the
    two helpers used different filters — long-option STCs counted in
    ``_realized_in_year`` (the gains/losses source) but NOT in
    ``realized_pnl_split_by_year`` (the ST/LT source).

    Seed: an equity gain, an equity loss, AND a long-call STC sell.
    The long-call STC must NOT appear on the gains/losses side, matching
    the canonical helper that excludes options entirely from ST/LT
    classification (§1256 is folded in separately, not here).
    """
    opt = OptionDetails(strike=400.0, expiry=date(2026, 6, 19), call_put="C")
    trades = [
        # Equity buy + sell — gain $30
        Trade(
            account=schwab_account.display(),
            date=date(2026, 1, 5),
            ticker="AAPL",
            action="Buy",
            quantity=Decimal("1"),
            proceeds=Decimal("0"),
            cost_basis=Decimal("100"),
        ),
        Trade(
            account=schwab_account.display(),
            date=date(2026, 3, 1),
            ticker="AAPL",
            action="Sell",
            quantity=Decimal("1"),
            proceeds=Decimal("130"),
            cost_basis=Decimal("100"),
        ),
        # Equity buy + sell — loss $20
        Trade(
            account=schwab_account.display(),
            date=date(2026, 1, 5),
            ticker="UUUU",
            action="Buy",
            quantity=Decimal("1"),
            proceeds=Decimal("0"),
            cost_basis=Decimal("100"),
        ),
        Trade(
            account=schwab_account.display(),
            date=date(2026, 3, 1),
            ticker="UUUU",
            action="Sell",
            quantity=Decimal("1"),
            proceeds=Decimal("80"),
            cost_basis=Decimal("100"),
        ),
        # Long-call BTO + STC — would-be loss $50 IF options counted
        Trade(
            account=schwab_account.display(),
            date=date(2026, 2, 1),
            ticker="SPY",
            action="Buy",
            quantity=Decimal("1"),
            proceeds=Decimal("0"),
            cost_basis=Decimal("300"),
            basis_source="option_long_open",
            option_details=opt,
        ),
        Trade(
            account=schwab_account.display(),
            date=date(2026, 3, 15),
            ticker="SPY",
            action="Sell",
            quantity=Decimal("1"),
            proceeds=Decimal("250"),
            cost_basis=Decimal("300"),
            basis_source="option_long_close",
            option_details=opt,
        ),
    ]
    seed_import(repo, schwab_account, trades)
    seed_lots(repo)

    b = compute_offset_budget(repo=repo, year=2026)
    # Pre-fix: gains=30, losses=-20-50=-70 (long-call STC counted).
    # Post-fix: gains=30, losses=-20 (long-call STC excluded — matches the
    # ST/LT source which the same OffsetBudget exposes elsewhere).
    assert b.realized_gains_ytd == Decimal("30")
    assert b.realized_losses_ytd == Decimal("-20")

    # The headline alignment: gross totals reconcile to the same net as the
    # ST/LT source. (Long-call STC excluded from both sides → net = $10.)
    st_pnl, lt_pnl = repo.realized_pnl_split_by_year(2026)
    sec1256_pnl = repo.section_1256_pnl(
        type("P", (), {"kind": "year", "label": "2026", "year": 2026})(),
        accounts=None,
    )
    sec1256_mtm = repo.section_1256_mtm_pnl(
        type("P", (), {"kind": "year", "label": "2026", "year": 2026})(),
        accounts=None,
    )
    canonical_net = st_pnl + lt_pnl + sec1256_pnl + sec1256_mtm
    assert b.realized_losses_ytd + b.realized_gains_ytd == canonical_net

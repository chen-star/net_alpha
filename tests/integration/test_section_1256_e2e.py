"""End-to-end: import a synthetic trade list → engine produces the correct mix of
wash-sale violations, exempt matches, and §1256 classifications.

Uses hand-built Trade objects instead of a raw CSV so the test does not depend
on the Schwab parser accepting a specific fixture format.  The import path is
real (repo.add_import → recompute_all), exercising the full engine stack.

Scenarios covered:
  - TSLA Sell at loss  + TSLA Buy within 30 days  → 1 wash-sale violation (regular equity)
  - SPY  Sell at loss  + VOO  Buy within 30 days  → 1 wash-sale violation (ETF pair)
  - SPX call Sell loss + SPX call Buy same series  → 1 ExemptMatch (§1256 exempt)
  - SPX call Buy + Sell pair that closes +$1000    → 1 Section1256Classification (60/40 split)
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register table metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all
from net_alpha.models.domain import ImportRecord, OptionDetails, Trade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_path, db_name: str = "e2e.db") -> Repository:
    engine = create_engine(f"sqlite:///{tmp_path}/{db_name}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def _seed(repo: Repository, trades: list[Trade]) -> None:
    """Plant a list of trades under a single import record."""
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="schwab_section_1256.csv",
        csv_sha256="golden_e2e",
        imported_at=datetime(2024, 12, 1),
        trade_count=len(trades),
    )
    repo.add_import(acct, rec, trades)


ACCOUNT = "schwab/personal"

# ---------------------------------------------------------------------------
# Trade fixtures
# ---------------------------------------------------------------------------

# --- TSLA wash sale (regular equity) ---
# Sell 10 TSLA at loss on 2024-10-01, buy 10 TSLA on 2024-10-15 (within 30d).
TSLA_SELL = Trade(
    date=date(2024, 10, 1),
    account=ACCOUNT,
    ticker="TSLA",
    action="Sell",
    quantity=10,
    proceeds=Decimal("2000"),
    cost_basis=Decimal("2500"),  # $500 loss
    basis_source="broker_csv",
    is_section_1256=False,
)
TSLA_BUY = Trade(
    date=date(2024, 10, 15),
    account=ACCOUNT,
    ticker="TSLA",
    action="Buy",
    quantity=10,
    proceeds=None,
    cost_basis=Decimal("2100"),
    basis_source="broker_csv",
    is_section_1256=False,
)

# --- SPY/VOO ETF-pair wash sale ---
# Sell 5 SPY at loss on 2024-10-05, buy 5 VOO on 2024-10-20 (within 30d).
SPY_SELL = Trade(
    date=date(2024, 10, 5),
    account=ACCOUNT,
    ticker="SPY",
    action="Sell",
    quantity=5,
    proceeds=Decimal("2200"),
    cost_basis=Decimal("2600"),  # $400 loss
    basis_source="broker_csv",
    is_section_1256=False,
)
VOO_BUY = Trade(
    date=date(2024, 10, 20),
    account=ACCOUNT,
    ticker="VOO",
    action="Buy",
    quantity=5,
    proceeds=None,
    cost_basis=Decimal("2300"),
    basis_source="broker_csv",
    is_section_1256=False,
)

# --- SPX call wash-sale exempt (§1256) ---
# Sell 1 SPX 4500C Dec-2025 at loss on 2024-10-08, buy same series on 2024-10-22 (within 30d).
# Both are §1256 contracts → ExemptMatch, NOT a violation.
SPX_OPT = OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C")
SPX_LOSS_SELL = Trade(
    date=date(2024, 10, 8),
    account=ACCOUNT,
    ticker="SPX",
    action="Sell",
    quantity=1,
    proceeds=Decimal("100"),
    cost_basis=Decimal("721.50"),  # $621.50 loss
    basis_source="broker_csv",
    option_details=SPX_OPT,
    is_section_1256=True,
)
SPX_REBUY = Trade(
    date=date(2024, 10, 22),
    account=ACCOUNT,
    ticker="SPX",
    action="Buy",
    quantity=1,
    proceeds=None,
    cost_basis=Decimal("150"),
    basis_source="broker_csv",
    option_details=SPX_OPT,
    is_section_1256=True,
)

# --- SPX call closed for +$1000 profit (§1256 60/40 classification) ---
# Use a DIFFERENT series (different strike) to avoid interference with the loss trade above.
SPX_PROFIT_OPT = OptionDetails(strike=5000, expiry=date(2025, 6, 20), call_put="C")
SPX_PROFIT_BUY = Trade(
    date=date(2024, 9, 1),
    account=ACCOUNT,
    ticker="SPX",
    action="Buy",
    quantity=1,
    proceeds=None,
    cost_basis=Decimal("500"),
    basis_source="broker_csv",
    option_details=SPX_PROFIT_OPT,
    is_section_1256=True,
)
SPX_PROFIT_SELL = Trade(
    date=date(2024, 11, 1),
    account=ACCOUNT,
    ticker="SPX",
    action="Sell",
    quantity=1,
    proceeds=Decimal("1500"),   # $1000 gain on top of $500 basis
    cost_basis=Decimal("500"),
    basis_source="broker_csv",
    option_details=SPX_PROFIT_OPT,
    is_section_1256=True,
)

ALL_TRADES = [
    TSLA_SELL, TSLA_BUY,
    SPY_SELL, VOO_BUY,
    SPX_LOSS_SELL, SPX_REBUY,
    SPX_PROFIT_BUY, SPX_PROFIT_SELL,
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_repo(tmp_path):
    repo = _make_repo(tmp_path)
    _seed(repo, ALL_TRADES)
    recompute_all(repo)
    return repo


def test_e2e_two_wash_sale_violations(fresh_repo):
    """TSLA + SPY/VOO → exactly 2 regular wash-sale violations."""
    violations = fresh_repo.all_violations()
    assert len(violations) == 2, f"Expected 2 violations, got {len(violations)}: {[v.ticker for v in violations]}"
    tickers = {v.ticker for v in violations}
    assert tickers == {"TSLA", "SPY"}


def test_e2e_tsla_violation_confirmed(fresh_repo):
    """TSLA same-stock wash sale → Confirmed confidence."""
    violations = fresh_repo.all_violations()
    tsla_v = next(v for v in violations if v.ticker == "TSLA")
    assert tsla_v.confidence == "Confirmed"
    assert tsla_v.disallowed_loss == pytest.approx(500.0)


def test_e2e_spy_voo_violation_unclear(fresh_repo):
    """SPY/VOO ETF-pair wash sale → Unclear confidence (see matcher.py)."""
    violations = fresh_repo.all_violations()
    spy_v = next(v for v in violations if v.ticker == "SPY")
    assert spy_v.confidence == "Unclear"


def test_e2e_spx_exempt_match(fresh_repo):
    """SPX call loss + SPX call rebuy → exactly 1 ExemptMatch with section_1256 reason."""
    exempts = fresh_repo.list_exempt_matches()
    assert len(exempts) == 1, f"Expected 1 exempt match, got {len(exempts)}"
    em = exempts[0]
    assert em.ticker == "SPX"
    assert em.exempt_reason == "section_1256"


def test_e2e_spx_no_wash_sale_violation(fresh_repo):
    """§1256 pair must NOT produce a regular wash-sale violation (SPX)."""
    violations = fresh_repo.all_violations()
    spx_violations = [v for v in violations if v.ticker == "SPX"]
    assert spx_violations == [], f"Expected no SPX violations, got {spx_violations}"


def test_e2e_section_1256_classification_60_40(fresh_repo):
    """Closed SPX 5000C profit → 1 §1256 classification with correct 60/40 split."""
    classifications = fresh_repo.list_section_1256_classifications()
    # Both SPX Sell trades produce a classification; isolate the profitable one
    # by filtering for realized_pnl > 0.
    profitable = [c for c in classifications if c.realized_pnl > 0]
    assert len(profitable) == 1, (
        f"Expected 1 profitable §1256 classification, got {len(profitable)}: "
        f"{[(c.underlying, c.realized_pnl) for c in classifications]}"
    )
    c = profitable[0]
    assert c.underlying == "SPX"
    expected_pnl = Decimal("1000")
    assert c.realized_pnl == pytest.approx(expected_pnl, abs=Decimal("0.01"))
    assert c.long_term_portion == pytest.approx(Decimal("600"), abs=Decimal("0.01"))
    assert c.short_term_portion == pytest.approx(Decimal("400"), abs=Decimal("0.01"))
    total = c.long_term_portion + c.short_term_portion
    assert total == pytest.approx(c.realized_pnl, abs=Decimal("0.01"))

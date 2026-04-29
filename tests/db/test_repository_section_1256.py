from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register SQLModel metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ExemptMatch, Section1256Classification


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def _exempt(ticker="SPX", loss_id="1", buy_id="2") -> ExemptMatch:
    return ExemptMatch(
        loss_trade_id=loss_id,
        triggering_buy_id=buy_id,
        exempt_reason="section_1256",
        rule_citation="IRC §1256(c)",
        notional_disallowed=Decimal("621.50"),
        confidence="Confirmed",
        matched_quantity=50,
        loss_account="schwab/personal",
        buy_account="schwab/personal",
        loss_sale_date=date(2024, 9, 15),
        triggering_buy_date=date(2024, 9, 22),
        ticker=ticker,
    )


def _classification(trade_id="100", underlying="SPX", pnl=Decimal("1000")) -> Section1256Classification:
    return Section1256Classification(
        trade_id=trade_id,
        realized_pnl=pnl,
        long_term_portion=pnl * Decimal("0.60"),
        short_term_portion=pnl * Decimal("0.40"),
        underlying=underlying,
    )


def test_save_exempt_match_and_list(repo):
    repo.save_exempt_matches([_exempt()])
    rows = repo.list_exempt_matches()
    assert len(rows) == 1
    assert rows[0].ticker == "SPX"
    assert rows[0].notional_disallowed == Decimal("621.50")


def test_clear_exempt_matches(repo):
    repo.save_exempt_matches([_exempt(loss_id="1", buy_id="2"), _exempt(loss_id="3", buy_id="4")])
    repo.clear_exempt_matches()
    assert repo.list_exempt_matches() == []


def test_save_classification_and_list(repo):
    repo.save_section_1256_classifications([_classification()])
    rows = repo.list_section_1256_classifications()
    assert len(rows) == 1
    assert rows[0].long_term_portion == Decimal("600")


def test_classifications_unique_per_trade(repo):
    repo.save_section_1256_classifications([_classification(pnl=Decimal("100"))])
    repo.save_section_1256_classifications([_classification(pnl=Decimal("200"))])
    rows = repo.list_section_1256_classifications()
    assert len(rows) == 1
    assert rows[0].realized_pnl == Decimal("200")

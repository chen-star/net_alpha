from datetime import date

from net_alpha.audit.hygiene import collect_issues
from net_alpha.models.domain import Trade
from tests.audit.conftest import seed_import


def test_three_or_more_same_day_same_key_surface_info(repo, schwab_account):
    trades = [
        Trade(
            account="Schwab/Tax",
            date=date(2026, 1, 1),
            ticker="AAPL",
            action="Buy",
            quantity=10,
            cost_basis=1000.0,
            occurrence_index=0,
        ),
        Trade(
            account="Schwab/Tax",
            date=date(2026, 1, 1),
            ticker="AAPL",
            action="Buy",
            quantity=10,
            cost_basis=1000.0,
            occurrence_index=1,
        ),
        Trade(
            account="Schwab/Tax",
            date=date(2026, 1, 1),
            ticker="AAPL",
            action="Buy",
            quantity=10,
            cost_basis=1000.0,
            occurrence_index=2,
        ),
    ]
    seed_import(repo, schwab_account, trades)

    issues = [i for i in collect_issues(repo) if i.category == "dup_key"]
    # 3 occurrences on the same day → 1 cluster surfaced (info severity).
    assert len(issues) == 1
    assert issues[0].severity == "info"
    assert "AAPL" in issues[0].summary

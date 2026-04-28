from datetime import date

from net_alpha.audit.hygiene import collect_issues
from net_alpha.models.domain import Trade
from tests.audit.conftest import seed_import


def test_sell_without_prior_buy_surfaces_warn(repo, schwab_account):
    # A sell of XYZ but no buy lots for XYZ — orphan.
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax",
                date=date(2026, 4, 1),
                ticker="XYZ",
                action="Sell",
                quantity=5,
                proceeds=500.0,
                cost_basis=400.0,
            )
        ],
    )
    issues = [i for i in collect_issues(repo) if i.category == "orphan_sell"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "XYZ" in issues[0].summary
    assert "missing prior-year import" in issues[0].detail.lower()

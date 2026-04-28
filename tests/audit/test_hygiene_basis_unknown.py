from datetime import date

from net_alpha.audit.hygiene import collect_issues
from net_alpha.models.domain import Trade
from tests.audit.conftest import seed_import


def test_basis_unknown_trade_links_to_ticker_page(repo, schwab_account):
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax",
                date=date(2026, 1, 1),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                cost_basis=None,
                basis_unknown=True,
                basis_source="transfer_in",
            )
        ],
    )
    # Find the actual DB-assigned trade id.
    trades = repo.all_trades()
    assert len(trades) == 1
    actual_trade_id = trades[0].id

    issues = [i for i in collect_issues(repo) if i.category == "basis_unknown"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "error"
    assert "AAPL" in issue.summary
    assert issue.fix_form is None
    # Link goes to the ticker detail page (single edit point).
    assert issue.fix_url is not None
    assert issue.fix_url.startswith("/ticker/AAPL")
    assert actual_trade_id in issue.fix_url

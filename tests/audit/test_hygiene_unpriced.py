from datetime import date

from net_alpha.audit.hygiene import collect_issues
from net_alpha.models.domain import Trade
from tests.audit.conftest import seed_import


def test_unpriced_symbol_surfaces_warn_issue(repo, schwab_account, monkeypatch):
    seed_import(
        repo,
        schwab_account,
        [
            Trade(
                account="Schwab/Tax",
                date=date(2026, 1, 1),
                ticker="DEAD",
                action="Buy",
                quantity=10,
                cost_basis=1000.0,
            )
        ],
    )
    # Stub the unpriced check to declare DEAD unpriced.
    from net_alpha.audit import hygiene as h

    monkeypatch.setattr(h, "_get_unpriced_symbols", lambda repo: ["DEAD"])

    issues = collect_issues(repo)
    unpriced = [i for i in issues if i.category == "unpriced"]
    assert len(unpriced) == 1
    # Unpriced is informational: there's no in-app fix for a missing Yahoo
    # quote (it's environmental — delisted, OTC, or symbol mismatch). The
    # severity dropped from warn to info and the misleading "go fix" link
    # was removed since /holdings has no manual-price-override UI.
    assert unpriced[0].severity == "info"
    assert "DEAD" in unpriced[0].summary
    assert unpriced[0].fix_url is None

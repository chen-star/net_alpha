from datetime import date

from net_alpha.audit.provenance import CashRef, provenance_for
from net_alpha.models.domain import CashEvent
from tests.audit.conftest import seed_import


def test_cash_provenance_lists_all_events(repo, schwab_account):
    events = [
        CashEvent(account="Schwab/Tax", event_date=date(2026, 1, 5),
                  kind="transfer_in", amount=10000.0),
        CashEvent(account="Schwab/Tax", event_date=date(2026, 2, 1),
                  kind="dividend", amount=42.0, ticker="AAPL"),
    ]
    seed_import(repo, schwab_account, [], cash_events=events)

    ref = CashRef(kind="cash", account_id=schwab_account.id)
    trace = provenance_for(ref, repo)
    assert len(trace.cash_events) == 2
    assert trace.total == 10042.0

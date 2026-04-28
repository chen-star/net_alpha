from datetime import date

from net_alpha.audit.provenance import NetContributedRef, Period, provenance_for
from net_alpha.models.domain import CashEvent
from tests.audit.conftest import seed_import


def test_net_contributed_only_includes_transfers(repo, schwab_account):
    events = [
        CashEvent(account="Schwab/Tax", event_date=date(2026, 1, 5), kind="transfer_in", amount=10000.0),
        CashEvent(account="Schwab/Tax", event_date=date(2026, 2, 1), kind="dividend", amount=42.0),
        CashEvent(account="Schwab/Tax", event_date=date(2026, 3, 1), kind="transfer_out", amount=2000.0),
    ]
    seed_import(repo, schwab_account, [], cash_events=events)

    ref = NetContributedRef(
        kind="net_contributed",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=schwab_account.id,
    )
    trace = provenance_for(ref, repo)
    # Net contributed = transfer_in − transfer_out; dividend excluded.
    assert trace.total == 8000.0
    kinds = {e.kind for e in trace.cash_events}
    assert kinds == {"transfer_in", "transfer_out"}

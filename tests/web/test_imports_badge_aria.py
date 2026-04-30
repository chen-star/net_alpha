"""Top-nav imports badge has aria-label and title for accessibility."""

import re
from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.audit._badge_cache import _cache
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade


def test_imports_badge_has_aria_and_title(client: TestClient, repo: Repository):
    """Imports badge in top-nav must have aria-label and title attributes."""
    _cache.invalidate()

    # Seed an import with a data hygiene issue (basis_unknown=True) so badge count > 0
    account = repo.get_or_create_account("Schwab", "Tax")
    trade = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=None,
        basis_unknown=True,
        basis_source="transfer_in",
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="test-sha",
        imported_at=datetime.now(),
        trade_count=1,
    )
    repo.add_import(account, record, [trade])

    # Fetch the home page and check for aria-label and title
    response = client.get("/")
    html = response.text

    # The badge span should have aria-label="N imports" and title="N imports"
    assert re.search(r'aria-label="\d+ imports"', html), "imports badge missing aria-label"
    assert re.search(r'title="\d+ imports"', html), "imports badge missing title"

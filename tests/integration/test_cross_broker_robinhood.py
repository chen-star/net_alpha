"""Cross-broker wash sale: loss closed on Schwab, rebuy on Robinhood within 30 days.

The wash-sale engine has been cross-broker since v1 (tests/engine/test_detector.py
covers the pure-function path). This test confirms the *ingest plumbing* — CSV
parse, Repository.add_import, recompute_all_violations — works for a cross-broker
scenario via the same seam users hit through the web upload + CLI.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from net_alpha.brokers.registry import detect_broker
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.models.domain import ImportRecord

# ---------------------------------------------------------------------------
# Minimal CSV content
# ---------------------------------------------------------------------------

# Schwab: buy 100 GPRO on 01/02 (well outside the 30-day window), sell at loss
# on 06/15 ($500 cost - $200 proceeds = $300 loss).  The original buy is more
# than 30 days before the sell, so it is NOT a replacement purchase and cannot
# trigger the wash-sale rule on its own.
_SCHWAB_CSV = """\
Date,Action,Symbol,Description,Quantity,Price,Amount
01/02/2024,Buy,GPRO,GoPro Inc,100,5.00,-500.00
06/15/2024,Sell,GPRO,GoPro Inc,100,2.00,200.00
"""

# Robinhood: rebuy 100 GPRO on 06/20 — 5 days after the 06/15 loss sell,
# well within the 30-day wash-sale window → should be flagged as a cross-broker
# wash sale with buy_account = robinhood/personal.
_ROBINHOOD_CSV = """\
Activity Date,Instrument,Trans Code,Quantity,Price,Amount
06/20/2024,GPRO,Buy,100,3.00,-300.00
"""


def _parse_rows(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text)))


def _import(repo, csv_text: str, expected_broker: str, label: str):
    rows = _parse_rows(csv_text)
    headers = list(rows[0].keys())
    parser = detect_broker(headers)
    assert parser is not None, f"No parser detected for headers: {headers}"
    assert parser.name == expected_broker, f"Expected {expected_broker!r}, got {parser.name!r}"

    acct = repo.get_or_create_account(expected_broker, label)
    result = parser.parse_full(rows, f"{expected_broker}/{label}")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename=f"{expected_broker}.csv",
        csv_sha256="x" * 64,
        imported_at=datetime(2024, 7, 1),
        trade_count=len(result.trades),
    )
    repo.add_import(acct, rec, result.trades, cash_events=result.cash_events)
    stitch_account(repo, acct.id)
    return acct


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_loss_on_schwab_then_rebuy_on_robinhood_triggers_wash_sale(repo):
    """Ingest Schwab loss + Robinhood rebuy → engine detects cross-broker wash sale."""
    _import(repo, _SCHWAB_CSV, "schwab", "personal")
    _import(repo, _ROBINHOOD_CSV, "robinhood", "personal")

    recompute_all_violations(repo, load_etf_pairs())

    violations = repo.all_violations()
    assert len(violations) == 1, (
        f"Expected exactly 1 wash-sale violation, got {len(violations)}: {violations}"
    )
    v = violations[0]
    assert v.disallowed_loss > 0, f"disallowed_loss should be positive, got {v.disallowed_loss}"
    assert "schwab" in v.loss_account.lower(), (
        f"loss_account should reference 'schwab', got {v.loss_account!r}"
    )
    assert "robinhood" in v.buy_account.lower(), (
        f"buy_account should reference 'robinhood', got {v.buy_account!r}"
    )

"""Schwab Realized G/L parser must tolerate sentinel tokens in money cells.

Regression for the I9 bug: Schwab writes ``'--'`` (or sometimes ``'N/A'``)
in money cells for rows with no broker history — typically inbound
transfers and gifts. ``_parse_money`` called ``float()`` directly with no
sentinel handling, so a single such row aborted the entire G/L import
with ``ValueError``.

The same tolerance already exists in ``import_/positions_csv._f``; the
GL parser was just missing it.
"""

from __future__ import annotations

import pytest

from net_alpha.brokers.schwab_realized_gl import SchwabRealizedGLParser


def _gl_rows(unadjusted_cost: str) -> list[dict[str, str]]:
    """Build a minimal one-row GL fixture with the given Unadjusted Cost
    cell text."""
    return [
        {
            "Symbol": "WRD",
            "Closed Date": "04/20/2026",
            "Opened Date": "02/11/2026",
            "Quantity": "100",
            "Proceeds": "$824.96",
            "Cost Basis (CB)": "$800.66",
            "Unadjusted Cost Basis": unadjusted_cost,
            "Wash Sale?": "No",
            "Disallowed Loss": "",
            "Term": "Short Term",
        }
    ]


@pytest.mark.parametrize("sentinel", ["--", "N/A", "n/a", ""])
def test_parser_accepts_sentinel_unadjusted_cost(sentinel):
    """Each sentinel should fall through cleanly (no ValueError, returns 0.0)."""
    parser = SchwabRealizedGLParser()
    lots = parser.parse(_gl_rows(sentinel), account_display="schwab/personal")
    assert len(lots) == 1
    # Empty/sentinel falls back to Cost Basis (CB) per parser intent for "",
    # or to 0.0 for explicit sentinels. The point is: no crash.


def test_parser_does_not_crash_on_mixed_sentinel_rows():
    """A batch with one good row + one '--' row imports the good one and the
    sentinel row without aborting the import."""
    parser = SchwabRealizedGLParser()
    rows = _gl_rows("--") + [
        {
            "Symbol": "AAPL",
            "Closed Date": "05/01/2026",
            "Opened Date": "01/15/2026",
            "Quantity": "50",
            "Proceeds": "$10000.00",
            "Cost Basis (CB)": "$8000.00",
            "Unadjusted Cost Basis": "$8000.00",
            "Wash Sale?": "No",
            "Disallowed Loss": "",
            "Term": "Short Term",
        }
    ]
    lots = parser.parse(rows, account_display="schwab/personal")
    assert len(lots) == 2
    aapl = next(lot for lot in lots if lot.ticker == "AAPL")
    assert aapl.unadjusted_cost_basis == 8000.0

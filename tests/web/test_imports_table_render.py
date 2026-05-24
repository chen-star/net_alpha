"""_imports_table.html must label positions-snapshot imports as 'positions',
not 'trades'. A positions CSV stores its row count in trade_count (FK
placeholder import), but those are holdings, not trades."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env():
    return Environment(
        loader=FileSystemLoader("src/net_alpha/web/templates"),
        autoescape=select_autoescape(),
    )


def _imp(**kw):
    base = dict(
        id=1,
        imported_at=datetime(2026, 5, 17, 17, 51),
        account_display="schwab/st",
        csv_filename="Short_Term_Transactions.csv",
        trade_count=0,
        gl_lot_count=0,
        cash_event_count=0,
        duplicate_trades=0,
        min_trade_date=None,
        max_trade_date=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_positions_import_labeled_as_positions_not_trades():
    positions_imp = _imp(
        id=18,
        csv_filename="[positions] as of 2026-05-17",
        trade_count=48,
        account_display="positions/(multi)",
    )
    out = _env().get_template("_imports_table.html").render(imports=[positions_imp], page=1)
    assert "48 positions" in out
    assert "48 trades" not in out
    # Delete confirm must use the positions-snapshot wording, not "Wash sales recomputed".
    assert "positions snapshot" in out
    assert "48 trades, 0 G/L lots" not in out


def test_trade_import_still_labeled_as_trades():
    trade_imp = _imp(id=15, csv_filename="Short_Term_Transactions.csv", trade_count=17)
    out = _env().get_template("_imports_table.html").render(imports=[trade_imp], page=1)
    assert "17 trades" in out

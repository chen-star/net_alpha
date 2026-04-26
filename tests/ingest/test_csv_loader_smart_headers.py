from pathlib import Path

from net_alpha.ingest.csv_loader import load_csv


def _write(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_load_csv_no_preamble_works_unchanged(tmp_path):
    """Backwards compat: a file with headers on row 0 still loads correctly."""
    path = _write(
        tmp_path,
        "tx.csv",
        "Date,Action,Symbol,Quantity,Amount\n01/02/2026,Buy,AAPL,1,$100.00\n",
    )
    headers, rows = load_csv(path)
    assert headers == ["Date", "Action", "Symbol", "Quantity", "Amount"]
    assert len(rows) == 1
    assert rows[0]["Action"] == "Buy"


def test_load_csv_skips_title_row_before_headers(tmp_path):
    """G/L pattern: a title row with one populated cell precedes the real headers."""
    path = _write(
        tmp_path,
        "gl.csv",
        '"Realized Gain/Loss - Lot Details for Short_Term as of ...","","","",""\n'
        '"Symbol","Closed Date","Quantity","Proceeds","Cost Basis (CB)"\n'
        '"WRD","04/20/2026","100","$824.96","$800.66"\n',
    )
    headers, rows = load_csv(path)
    assert headers == ["Symbol", "Closed Date", "Quantity", "Proceeds", "Cost Basis (CB)"]
    assert len(rows) == 1
    assert rows[0]["Symbol"] == "WRD"


def test_load_csv_detects_headers_within_first_five_rows(tmp_path):
    """Multiple title/blank rows still allowed before headers."""
    path = _write(
        tmp_path,
        "weird.csv",
        '"Title row","","",""\n'
        '"","","",""\n'
        '"Generated 2026-04-25","","",""\n'
        '"Symbol","Closed Date","Quantity","Cost Basis (CB)"\n'
        '"AAPL","04/20/2026","10","$100.00"\n',
    )
    headers, rows = load_csv(path)
    assert headers == ["Symbol", "Closed Date", "Quantity", "Cost Basis (CB)"]
    assert rows[0]["Symbol"] == "AAPL"


def test_load_csv_rejects_when_no_header_row_found(tmp_path):
    """If first 5 rows all look like data (start with $ or date), give up."""
    path = _write(
        tmp_path,
        "bad.csv",
        "$1,$2,$3\n01/02/2026,03/04/2026,05/06/2026\n$4,$5,$6\n",
    )
    headers, rows = load_csv(path)
    # Falls back to the FIRST row as headers (legacy behavior, no exception).
    # The parser registry will then fail to match any parser, surfacing a clean error.
    assert headers == ["$1", "$2", "$3"]

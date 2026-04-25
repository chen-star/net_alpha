from net_alpha.ingest.csv_loader import load_csv


def test_loads_headers_and_rows(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Date,Action,Symbol\n06/15/2024,Buy,TSLA\n")
    headers, rows = load_csv(str(p))
    assert headers == ["Date", "Action", "Symbol"]
    assert rows == [{"Date": "06/15/2024", "Action": "Buy", "Symbol": "TSLA"}]


def test_csv_sha256_is_deterministic(tmp_path):
    from net_alpha.ingest.csv_loader import compute_csv_sha256

    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n")
    assert compute_csv_sha256(str(p)) == compute_csv_sha256(str(p))

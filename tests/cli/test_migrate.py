import sqlite3

import pytest
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    yield


def test_migrate_from_v1_imports_v1_trades(tmp_path):
    # Build a minimal v1 DB with one trade
    v1_path = tmp_path / ".net_alpha" / "net_alpha.db"
    v1_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(v1_path))
    con.execute(
        "CREATE TABLE trades (id TEXT, account TEXT, date TEXT, ticker TEXT, "
        "action TEXT, quantity REAL, proceeds REAL, cost_basis REAL)"
    )
    con.execute("INSERT INTO trades VALUES ('u1', 'schwab', '2024-06-15', 'TSLA', 'Buy', 10, NULL, 2000.0)")
    con.commit()
    con.close()

    from net_alpha.cli.app import app

    res = CliRunner().invoke(app, ["migrate-from-v1", "--yes"])
    assert res.exit_code == 0, res.output
    assert "Migrated" in res.stdout

    # Confirm v2 DB exists and has the trade
    v2_path = tmp_path / ".net_alpha" / "net_alpha.db.v2"
    assert v2_path.exists()
    con2 = sqlite3.connect(str(v2_path))
    n = con2.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    assert n == 1

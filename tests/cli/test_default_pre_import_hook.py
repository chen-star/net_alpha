from __future__ import annotations

import sqlite3
from pathlib import Path

from net_alpha.cli import default as default_cmd


def test_pre_import_hook_creates_bundle(tmp_path, monkeypatch):
    """A `net-alpha <csv>` invocation snapshots before committing the import."""
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    # Initialize an empty DB so the engine can open it.
    con = sqlite3.connect(data / "net_alpha.db")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', '20')")
    con.commit()
    con.close()

    # Minimal Schwab CSV with no rows; the parser will produce zero trades but the hook should still fire.
    csv = tmp_path / "schwab.csv"
    csv.write_text(
        '"Transactions for account ...XXXX as of 2026-05-07"\n'
        '"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n'
    )

    rc = default_cmd.run([str(csv)], account_label="test/main", detail=False)
    assert rc in (0, 1)  # body may exit with code 1 if no rows; hook fires either way

    bundles = list((data / "backups").glob("wash-alpha-*-pre-import.tar.gz"))
    assert len(bundles) == 1

from __future__ import annotations

import sqlite3

from net_alpha.cli import migrate as migrate_cmd


def test_pre_migrate_hook_creates_bundle(tmp_path, monkeypatch):
    """A `migrate-from-v1` invocation snapshots before mutating state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    data = tmp_path / ".net_alpha"
    data.mkdir()
    # Pre-create a v1 DB so the migration enters its body.
    v1 = data / "net_alpha.db"
    con = sqlite3.connect(v1)
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '1')")
    con.execute(
        "CREATE TABLE trades (account TEXT, date TEXT, ticker TEXT, action TEXT,"
        " quantity REAL, proceeds REAL, cost_basis REAL)"
    )
    con.commit()
    con.close()

    rc = migrate_cmd.run(yes=True)
    # Even if migration completes successfully (returns 0) or no-ops, the hook should fire.
    assert rc in (0, 1)

    bundles = list((data / "backups").glob("wash-alpha-*-pre-migrate.tar.gz"))
    assert len(bundles) == 1

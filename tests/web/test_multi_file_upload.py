from __future__ import annotations

from pathlib import Path

GL_FIXTURE = Path(__file__).parent.parent / "brokers" / "fixtures" / "schwab_realized_gl_min.csv"
TX_FIXTURE = Path(__file__).parent / "fixtures" / "schwab_minimal.csv"


def test_preview_with_two_files_returns_per_file_detection(client):
    with TX_FIXTURE.open("rb") as tx, GL_FIXTURE.open("rb") as gl:
        resp = client.post(
            "/imports/preview",
            files=[
                ("files", ("schwab_tx.csv", tx, "text/csv")),
                ("files", ("schwab_gl.csv", gl, "text/csv")),
            ],
        )
    assert resp.status_code == 200
    body = resp.text.lower()
    assert "schwab" in body
    assert "transaction" in body or "trades" in body
    assert "g/l" in body or "realized" in body or "lot" in body


def test_preview_with_unrecognized_file_includes_warning(client, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("totally,unknown,format\n1,2,3\n")
    with TX_FIXTURE.open("rb") as tx, bad.open("rb") as b:
        resp = client.post(
            "/imports/preview",
            files=[
                ("files", ("schwab_tx.csv", tx, "text/csv")),
                ("files", ("bad.csv", b, "text/csv")),
            ],
        )
    assert resp.status_code == 200
    assert "unrecogniz" in resp.text.lower() or "unknown" in resp.text.lower()


def test_upload_two_files_creates_import_and_gl_lots(client, repo):
    with TX_FIXTURE.open("rb") as tx, GL_FIXTURE.open("rb") as gl:
        resp = client.post(
            "/imports",
            files=[
                ("files", ("schwab_tx.csv", tx, "text/csv")),
                ("files", ("schwab_gl.csv", gl, "text/csv")),
            ],
            data={"account": "personal"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    imports = repo.list_imports()
    assert len(imports) >= 1
    acct = repo.get_account("schwab", "personal")
    assert acct is not None
    gl_lots = repo.get_gl_lots_for_ticker(acct.id, "WRD")
    assert len(gl_lots) == 1


def test_upload_only_transactions_runs_fifo_fallback(client, repo):
    """A pure transactions upload still produces useful violations via FIFO fallback."""
    with TX_FIXTURE.open("rb") as tx:
        resp = client.post(
            "/imports",
            files=[("files", ("schwab_tx.csv", tx, "text/csv"))],
            data={"account": "personal"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    # The TSLA loss + rebuy fixture should still produce >= 1 violation via FIFO basis.
    assert len(repo.all_violations()) >= 1


def test_upload_only_gl_succeeds_without_transactions(client, repo):
    """G/L-only upload: G/L lots are stored, no Sells exist to hydrate, no error."""
    with GL_FIXTURE.open("rb") as gl:
        resp = client.post(
            "/imports",
            files=[("files", ("schwab_gl.csv", gl, "text/csv"))],
            data={"account": "personal"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    acct = repo.get_account("schwab", "personal")
    assert acct is not None
    assert len(repo.get_gl_lots_for_ticker(acct.id, "WRD")) == 1


def test_upload_zero_recognized_files_returns_400(client, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("totally,unknown,format\n1,2,3\n")
    with bad.open("rb") as b:
        resp = client.post(
            "/imports",
            files=[("files", ("bad.csv", b, "text/csv"))],
            data={"account": "personal"},
            follow_redirects=False,
        )
    assert resp.status_code == 400


def test_remove_import_with_gl_clears_orphan_lots(client, repo):
    """Removing a G/L-only import via DELETE /imports/{id} must remove the
    G/L lots and re-stitch so any previously hydrated sells are demoted."""
    with GL_FIXTURE.open("rb") as gl:
        client.post(
            "/imports",
            files=[("files", ("schwab_gl.csv", gl, "text/csv"))],
            data={"account": "personal"},
            follow_redirects=False,
        )
    acct = repo.get_account("schwab", "personal")
    assert acct is not None
    assert len(repo.get_gl_lots_for_ticker(acct.id, "WRD")) == 1
    imports = repo.list_imports()
    assert len(imports) == 1
    import_id = imports[0].id
    resp = client.delete(f"/imports/{import_id}")
    assert resp.status_code == 200
    assert len(repo.get_gl_lots_for_ticker(acct.id, "WRD")) == 0

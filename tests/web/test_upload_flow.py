from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "schwab_minimal.csv"


def test_preview_returns_modal_with_detected_broker(client):
    with FIXTURE.open("rb") as f:
        resp = client.post(
            "/imports/preview",
            files=[("files", ("schwab.csv", f, "text/csv"))],
        )
    assert resp.status_code == 200
    assert "transaction" in resp.text.lower() or "trades" in resp.text.lower()


def test_upload_full_flow_creates_import_and_violations(client, repo):
    with FIXTURE.open("rb") as f:
        resp = client.post(
            "/imports",
            files=[("files", ("schwab.csv", f, "text/csv"))],
            data={"account": "personal"},
            follow_redirects=False,
        )
    # Phase 1 IA critical fix #3: redirects to settings drawer instead of /imports?flash=...
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings/imports"
    imports = repo.list_imports()
    assert len(imports) == 1
    assert imports[0].account_display == "schwab/personal"
    assert imports[0].csv_filename == "schwab.csv"
    assert len(repo.all_violations()) >= 1


def test_upload_unrecognized_format_returns_modal_error(client, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("totally,unknown,format\n1,2,3\n")
    with bad.open("rb") as f:
        resp = client.post(
            "/imports/preview",
            files=[("files", ("bad.csv", f, "text/csv"))],
        )
    assert resp.status_code == 200
    assert "unrecogniz" in resp.text.lower() or "unknown" in resp.text.lower()

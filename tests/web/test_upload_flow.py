from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "schwab_minimal.csv"


def test_preview_returns_modal_with_detected_broker(client):
    with FIXTURE.open("rb") as f:
        resp = client.post("/imports/preview", files={"file": ("schwab.csv", f, "text/csv")})
    assert resp.status_code == 200
    assert "schwab" in resp.text.lower()
    assert "Account label" in resp.text or "account" in resp.text.lower()


def test_upload_full_flow_creates_import_and_violations(client, repo):
    with FIXTURE.open("rb") as f:
        resp = client.post(
            "/imports",
            files={"file": ("schwab.csv", f, "text/csv")},
            data={"account": "personal"},
            follow_redirects=False,
        )
    assert resp.status_code == 200
    imports = repo.list_imports()
    assert len(imports) == 1
    assert imports[0].account_display == "schwab/personal"
    assert imports[0].csv_filename == "schwab.csv"
    # The TSLA loss + rebuy within window must produce at least one violation.
    assert len(repo.all_violations()) >= 1


def test_upload_unrecognized_format_returns_modal_error(client, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("totally,unknown,format\n1,2,3\n")
    with bad.open("rb") as f:
        resp = client.post("/imports/preview", files={"file": ("bad.csv", f, "text/csv")})
    assert resp.status_code == 200
    # The apostrophe in "couldn't" is HTML-escaped to &#39; in the response.
    assert "couldn" in resp.text.lower() and "detect" in resp.text.lower()

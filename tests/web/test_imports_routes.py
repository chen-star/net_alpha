from datetime import date


def test_imports_page_empty_state(client):
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    assert "Imports" in resp.text
    assert "No imports yet" in resp.text


def test_imports_page_lists_imports(client, repo, builders):
    trades = [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1), qty=10, cost=1700)]
    builders.seed_import(repo, "schwab", "personal", trades, csv_filename="aapl.csv")
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    assert "schwab/personal" in resp.text
    assert "aapl.csv" in resp.text


def test_delete_import_removes_it_and_returns_table_fragment(client, repo, builders):
    _, import_id = builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
        csv_filename="aapl.csv",
    )
    assert len(repo.list_imports()) == 1

    resp = client.delete(f"/imports/{import_id}")
    assert resp.status_code == 200
    assert "No imports yet" in resp.text  # fragment shows empty state
    assert "DOCTYPE" not in resp.text  # raw fragment, not full page
    assert len(repo.list_imports()) == 0


def test_delete_nonexistent_import_returns_404(client):
    resp = client.delete("/imports/999")
    assert resp.status_code == 404


def test_imports_page_embeds_drop_zone(client):
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    body = resp.text
    # Drop-zone is embedded directly on the page (not behind a "+ New import" link).
    assert "drop-zone" in body
    assert "+ New import" not in body


def test_import_modal_reuses_drop_zone_file_input(client):
    """The modal must not contain its own file input — the drop-zone's
    `#csv-input` is associated with the modal form via the `form` attribute,
    so the originally-dropped files submit without a re-pick."""
    csv_bytes = b"Date,Action,Symbol,Quantity,Price,Amount\n"
    response = client.post(
        "/imports/preview",
        files={"files": ("x.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    html = response.text
    # Modal form has the id the drop-zone input points at.
    assert 'id="import-form"' in html
    # No second file input, no "Choose files" button, no re-attach hint.
    assert 'type="file"' not in html
    assert "Choose files" not in html
    assert "re-attach" not in html.lower()


def test_drop_zone_input_is_associated_with_import_form(client):
    """The drop-zone file input declares `form=\"import-form\"` so its FileList
    is submitted when the modal form is submitted."""
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    body = resp.text
    assert 'id="csv-input"' in body
    assert 'form="import-form"' in body


def test_imports_tab_disinherits_hx_select(client):
    """The settings drawer's Imports tab loader uses `hx-select=\"main > *\"`
    to strip page chrome from the lazy-loaded /imports/_legacy_page response.
    Without `hx-disinherit=\"hx-select\"`, child controls (drop-zone preview,
    delete button, set-basis Save) inherit that selector and end up swapping
    empty content into their target — silently blanking the import modal and
    the imports table."""
    resp = client.get("/settings/imports")
    assert resp.status_code == 200
    # Both the original selector and the disinherit must be present together.
    assert 'hx-select="main &gt; *"' in resp.text or 'hx-select="main > *"' in resp.text
    assert 'hx-disinherit="hx-select"' in resp.text


def test_bulk_delete_removes_selected_imports(client, repo, builders):
    _, id_a = builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
        csv_filename="a.csv",
    )
    _, id_b = builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "MSFT", date(2024, 6, 1))],
        csv_filename="b.csv",
    )
    _, id_c = builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "GOOG", date(2024, 7, 1))],
        csv_filename="c.csv",
    )
    assert len(repo.list_imports()) == 3

    resp = client.post("/imports/bulk-delete", data={"ids": [id_a, id_c]})
    assert resp.status_code == 200
    # Returns the table fragment, not a full page.
    assert "DOCTYPE" not in resp.text

    remaining = {imp.id for imp in repo.list_imports()}
    assert remaining == {id_b}


def test_bulk_delete_with_empty_selection_is_noop(client, repo, builders):
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
        csv_filename="a.csv",
    )
    resp = client.post("/imports/bulk-delete", data={})
    assert resp.status_code == 200
    assert len(repo.list_imports()) == 1


def test_bulk_delete_skips_unknown_ids(client, repo, builders):
    _, id_a = builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
        csv_filename="a.csv",
    )
    resp = client.post("/imports/bulk-delete", data={"ids": [id_a, 99999]})
    assert resp.status_code == 200
    assert repo.list_imports() == []


def test_imports_table_renders_bulk_delete_form(client, repo, builders):
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
        csv_filename="a.csv",
    )
    resp = client.get("/imports/_legacy_page")
    assert resp.status_code == 200
    body = resp.text
    assert 'id="bulk-imports-form"' in body
    assert 'hx-post="/imports/bulk-delete"' in body
    # One checkbox per row, posted as `ids`.
    assert 'name="ids"' in body
    assert "Delete selected" in body

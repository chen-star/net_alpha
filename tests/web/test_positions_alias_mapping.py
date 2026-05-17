"""End-to-end tests for the positions-CSV → account alias picker.

When a positions CSV's header account label doesn't match any user-named
account, the upload handler must redirect to a mapping page that lets
the user assign the broker label to an existing account in one click.
Submitting the picker registers the alias, retags the just-saved
broker_position rows, and re-runs verify.
"""

from __future__ import annotations


def _csv(header_account: str, body_rows: list[tuple[str, float, float, float]]) -> bytes:
    """Build a minimal Schwab per-account positions CSV with the given
    header account string + (symbol, qty, basis, mv) rows."""
    header = f'"Positions for account {header_account} as of  09:00 AM ET, 2026/05/17"\n'
    cols = '"Symbol","Description","Qty (Quantity)","Cost Basis","Mkt Val (Market Value)","Gain $ (Gain/Loss $)"\n'
    body = "".join(f'"{sym}","{sym} Inc","{qty}","${basis}","${mv}","$0.00"\n' for sym, qty, basis, mv in body_rows)
    return (header + cols + body).encode("utf-8")


def test_upload_with_unmapped_label_redirects_to_picker(client, repo):
    """Account label "Short Term ...180" matches no user account → picker."""
    repo.get_or_create_account("schwab", "st")
    csv = _csv("Short Term ...180", [("AAPL", 1.0, 100.0, 110.0)])

    resp = client.post(
        "/imports/positions",
        files={"file": ("positions.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/imports/positions/map")
    assert "import_id=" in location


def test_upload_with_already_aliased_label_skips_picker(client, repo):
    """Pre-registered alias → resolution happens inline → no picker."""
    acct = repo.get_or_create_account("schwab", "st")
    repo.set_account_broker_alias(account_id=acct.id, broker_label="Short Term ...180")

    csv = _csv("Short Term ...180", [("AAPL", 1.0, 100.0, 110.0)])
    resp = client.post(
        "/imports/positions",
        files={"file": ("positions.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/settings/imports")

    rows, _ = repo.latest_broker_positions()
    assert {r.account_label for r in rows} == {"schwab/st"}


def test_upload_with_label_matching_existing_label_skips_picker(client, repo):
    """Broker label literally equals an existing accounts.label → no picker."""
    repo.get_or_create_account("schwab", "st")
    csv = _csv("st", [("AAPL", 1.0, 100.0, 110.0)])

    resp = client.post(
        "/imports/positions",
        files={"file": ("positions.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/settings/imports")


def test_picker_get_lists_unresolved_labels_and_account_options(client, repo):
    """GET /imports/positions/map renders one row per unresolved label,
    each with a dropdown of all user accounts."""
    repo.get_or_create_account("schwab", "st")
    repo.get_or_create_account("schwab", "lt")
    import_id = repo.save_broker_positions(
        rows=[
            {
                "account_label": "Short Term ...180",
                "symbol": "AAPL",
                "qty": 1.0,
                "cost_basis": 100.0,
                "market_value": 110.0,
                "unrealized_pl": 10.0,
            }
        ],
        as_of_date="2026-05-17",
    )

    resp = client.get(f"/imports/positions/map?import_id={import_id}")
    assert resp.status_code == 200
    body = resp.text
    assert "Short Term ...180" in body
    # Both user-named accounts appear as picker options. The exact display
    # format is up to the template; what matters is each account.id shows
    # up inside an <option> alongside its label so the user can pick it.
    st_id = repo.get_account("schwab", "st").id
    lt_id = repo.get_account("schwab", "lt").id
    assert f'value="{st_id}"' in body
    assert f'value="{lt_id}"' in body
    # And the human-readable label for each is somewhere in the body.
    assert "st" in body
    assert "lt" in body


def test_picker_post_applies_alias_and_retags_rows(client, repo):
    """POST /imports/positions/map registers the alias, retags
    broker_position rows, and redirects to /verify."""
    acct = repo.get_or_create_account("schwab", "st")
    import_id = repo.save_broker_positions(
        rows=[
            {
                "account_label": "Short Term ...180",
                "symbol": "AAPL",
                "qty": 1.0,
                "cost_basis": 100.0,
                "market_value": 110.0,
                "unrealized_pl": 10.0,
            }
        ],
        as_of_date="2026-05-17",
    )

    resp = client.post(
        "/imports/positions/map",
        data={
            "import_id": str(import_id),
            # Form field name is "map[<broker_label>]" → account_id (or label)
            "broker_label": ["Short Term ...180"],
            "account_id": [str(acct.id)],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/verify"

    # Alias is set on the account; resolver returns the canonical display.
    assert repo.resolve_account_label("Short Term ...180") == "schwab/st"
    # broker_position rows are retagged to that same display form.
    rows, _ = repo.latest_broker_positions()
    assert {r.account_label for r in rows} == {"schwab/st"}

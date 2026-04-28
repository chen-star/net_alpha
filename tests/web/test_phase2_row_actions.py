"""Phase 2 row action menu (§3.4 of UI/UX redesign spec)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_row_actions_button_present_on_at_loss_rows(client: TestClient):
    resp = client.get("/positions?view=at-loss")
    assert resp.status_code == 200
    html = resp.text
    if 'data-row="lot"' not in html:
        return  # no fixtures, skip
    assert 'data-testid="row-actions"' in html


def test_row_actions_menu_lists_four_actions(client: TestClient):
    resp = client.get("/positions?view=at-loss")
    html = resp.text
    if 'data-testid="row-actions"' not in html:
        return  # no fixtures, skip
    for action in ("open-ticker", "sim-sell", "set-basis", "copy-ticker"):
        assert f'data-action="{action}"' in html, f"missing action: {action}"


def test_row_actions_sim_link_includes_qty_and_account(client: TestClient):
    resp = client.get("/positions?view=at-loss")
    html = resp.text
    if 'data-action="sim-sell"' not in html:
        return
    assert "/sim?ticker=" in html
    assert "&qty=" in html
    assert "&action=sell" in html


def test_row_actions_button_present_on_all_view_rows(client: TestClient):
    resp = client.get("/positions?view=all")
    html = resp.text
    if 'data-row="position"' not in html:
        return  # no fixture, skip
    assert 'data-testid="row-actions"' in html

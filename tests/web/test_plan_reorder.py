"""Tests for the Plan-tab Manual sort mode and POST /positions/plan/reorder."""

from decimal import Decimal

from net_alpha.targets.models import TargetUnit


def _seed_three(repo):
    repo.upsert_target("AAA", Decimal("1"), TargetUnit.USD)  # sort_order 1
    repo.upsert_target("BBB", Decimal("1"), TargetUnit.USD)  # sort_order 2
    repo.upsert_target("CCC", Decimal("1"), TargetUnit.USD)  # sort_order 3


def test_get_plan_manual_uses_manual_order(client, repo):
    _seed_three(repo)
    repo.set_target_order(["CCC", "AAA", "BBB"])

    resp = client.get("/positions?view=plan&sort=manual")
    assert resp.status_code == 200
    body = resp.text

    # Find the position of each row's data-symbol marker; CCC must come first.
    pos_ccc = body.find('data-symbol="CCC"')
    pos_aaa = body.find('data-symbol="AAA"')
    pos_bbb = body.find('data-symbol="BBB"')
    assert -1 < pos_ccc < pos_aaa < pos_bbb


def test_manual_option_present_in_toolbar(client, repo):
    _seed_three(repo)
    resp = client.get("/positions?view=plan&sort=manual")
    body = resp.text
    assert '<option value="manual"' in body
    # And it should be marked selected when sort=manual.
    assert 'value="manual"' in body and "selected" in body


def test_manual_mode_renders_handle_column(client, repo):
    _seed_three(repo)
    resp = client.get("/positions?view=plan&sort=manual")
    body = resp.text
    # The tbody is tagged for the JS to find.
    assert 'id="plan-tbody"' in body
    assert 'data-sort-mode="manual"' in body
    # Each row carries a drag-handle cell.
    assert body.count('class="drag-handle') >= 3


def test_alpha_mode_does_not_render_handle_column(client, repo):
    _seed_three(repo)
    resp = client.get("/positions?view=plan&sort=alpha")
    body = resp.text
    assert 'data-sort-mode="alpha"' in body
    assert 'class="drag-handle' not in body


def test_post_reorder_persists_and_rerenders(client, repo):
    _seed_three(repo)
    # Initial sort_order: AAA=1, BBB=2, CCC=3.

    resp = client.post(
        "/positions/plan/reorder",
        data={"order": ["CCC", "AAA", "BBB"]},
    )
    assert resp.status_code == 200
    body = resp.text

    # Response is the re-rendered plan body.
    assert 'id="plan-body"' in body
    pos_ccc = body.find('data-symbol="CCC"')
    pos_aaa = body.find('data-symbol="AAA"')
    pos_bbb = body.find('data-symbol="BBB"')
    assert -1 < pos_ccc < pos_aaa < pos_bbb

    # Persistence: subsequent GET sees the same order.
    resp2 = client.get("/positions?view=plan&sort=manual")
    body2 = resp2.text
    assert body2.find('data-symbol="CCC"') < body2.find('data-symbol="AAA"') < body2.find('data-symbol="BBB"')


def test_post_reorder_drops_unknown_symbols(client, repo):
    _seed_three(repo)
    resp = client.post(
        "/positions/plan/reorder",
        data={"order": ["BBB", "NOPE", "AAA"]},
    )
    assert resp.status_code == 200

    syms = [t.symbol for t in repo.list_targets_by_manual_order()]
    # NOPE is dropped; BBB → 1, AAA → 2; CCC keeps its old sort_order (3).
    assert syms[:2] == ["BBB", "AAA"]
    assert "CCC" in syms


def test_post_reorder_preserves_account_filter_in_render(client, repo):
    _seed_three(repo)
    resp = client.post(
        "/positions/plan/reorder?account=Schwab%2FBrokerage",
        data={"order": ["AAA", "BBB", "CCC"]},
    )
    assert resp.status_code == 200
    # The selected_account is propagated into the toolbar's hidden form input.
    assert 'name="account"' in resp.text
    assert 'value="Schwab/Brokerage"' in resp.text


def test_post_reorder_empty_list_is_noop(client, repo):
    _seed_three(repo)
    resp = client.post("/positions/plan/reorder", data={})
    assert resp.status_code == 200
    syms = [t.symbol for t in repo.list_targets_by_manual_order()]
    assert syms == ["AAA", "BBB", "CCC"]  # unchanged

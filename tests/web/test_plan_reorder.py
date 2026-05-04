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
    assert 'value="manual"' in body and 'selected' in body

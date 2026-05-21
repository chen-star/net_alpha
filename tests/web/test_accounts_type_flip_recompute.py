"""POST /settings/accounts must trigger a wash-sale recompute when the type
flip crosses the taxable ↔ tax-advantaged boundary.

Without this, classifying an account as IRA after the fact left every
existing cross-account WashSaleViolation stuck at kind="deferred" — the
deferred branch rolls the disallowed loss into the replacement lot's
adjusted_basis (§1091(d)), which is the wrong outcome under
Rev. Rul. 2008-5 (the loss is permanently disallowed and the replacement
lot's basis should remain at cost).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import Trade


def _seed_cross_account_wash_sale(repo, builders) -> None:
    """Seed a clean cross-account wash sale: loss in Tax, replacement in Roth.

    The opening Buy in Tax sits >30d before the Sell so it is NOT itself a
    wash-sale replacement candidate; the Roth Buy on day +10 is the only
    in-window buy. Both accounts default to taxable until the test flips one.
    """
    builders.seed_import(
        repo,
        "schwab",
        "Tax",
        [
            builders.make_buy("schwab/Tax", "AAPL", date(2025, 11, 1), qty=10.0, cost=2000.0),
            Trade(
                account="schwab/Tax",
                date=date(2026, 1, 10),
                ticker="AAPL",
                action="Sell",
                quantity=Decimal("10"),
                proceeds=Decimal("1500"),
                cost_basis=Decimal("2000"),
            ),
        ],
    )
    builders.seed_import(
        repo,
        "schwab",
        "Roth",
        [
            Trade(
                account="schwab/Roth",
                date=date(2026, 1, 20),
                ticker="AAPL",
                action="Buy",
                quantity=Decimal("10"),
                proceeds=None,
                cost_basis=Decimal("1550"),
            ),
        ],
    )


def test_type_flip_to_tax_advantaged_reclassifies_existing_violation(client: TestClient, repo, builders):
    _seed_cross_account_wash_sale(repo, builders)
    # Initial state: both accounts taxable → kind="deferred".
    recompute_all_violations(repo, load_etf_pairs())
    violations = [v for v in repo.all_violations() if v.ticker == "AAPL"]
    assert violations, "fixture didn't produce a violation"
    assert all(v.kind == "deferred" for v in violations), (
        f"expected deferred before flip, got {[v.kind for v in violations]}"
    )

    # Flip the Roth account (replacement leg) to roth_ira.
    resp = client.post(
        "/settings/accounts",
        data={"broker": "schwab", "label": "Roth", "type": "roth_ira"},
    )
    assert resp.status_code == 200

    # The route's recompute must have reclassified the violation kind.
    violations_after = [v for v in repo.all_violations() if v.ticker == "AAPL"]
    assert violations_after, "violation disappeared after flip"
    assert all(v.kind == "permanent_ira" for v in violations_after), (
        f"expected permanent_ira after flip, got {[v.kind for v in violations_after]}"
    )


def test_type_flip_back_to_taxable_reverts_classification(client: TestClient, repo, builders):
    _seed_cross_account_wash_sale(repo, builders)
    # Pre-flip Roth → trad_ira directly on the repo + recompute so we start
    # in the permanent_ira state.
    repo.set_account_type(broker="schwab", label="Roth", type_="trad_ira")
    recompute_all_violations(repo, load_etf_pairs())
    pre = [v for v in repo.all_violations() if v.ticker == "AAPL"]
    assert pre and all(v.kind == "permanent_ira" for v in pre), (
        f"setup expected permanent_ira, got {[v.kind for v in pre]}"
    )

    # Flip Roth back to taxable via the route.
    resp = client.post(
        "/settings/accounts",
        data={"broker": "schwab", "label": "Roth", "type": "taxable"},
    )
    assert resp.status_code == 200

    post = [v for v in repo.all_violations() if v.ticker == "AAPL"]
    assert post and all(v.kind == "deferred" for v in post), (
        f"expected deferred after revert, got {[v.kind for v in post]}"
    )


def test_type_flip_within_tax_advantaged_skips_recompute(client: TestClient, repo, builders, monkeypatch):
    """trad_ira → roth_ira must NOT change wash-sale classification — both
    are tax-advantaged, so the IRA-trap classifier output is identical.

    Spies on recompute_all_violations to confirm the route actually skips it
    (state-only assertion would pass even if the guard were removed, since
    the recompute is idempotent on this fixture)."""
    _seed_cross_account_wash_sale(repo, builders)
    repo.set_account_type(broker="schwab", label="Roth", type_="trad_ira")
    recompute_all_violations(repo, load_etf_pairs())
    before = [(v.id, v.kind) for v in repo.all_violations() if v.ticker == "AAPL"]
    assert before, "fixture didn't produce a violation"
    assert all(k == "permanent_ira" for _, k in before)

    calls: list[tuple] = []

    def _spy(repo_arg, pairs_arg):
        calls.append((repo_arg, pairs_arg))

    monkeypatch.setattr("net_alpha.web.routes.accounts.recompute_all_violations", _spy)

    resp = client.post(
        "/settings/accounts",
        data={"broker": "schwab", "label": "Roth", "type": "roth_ira"},
    )
    assert resp.status_code == 200
    assert calls == [], f"recompute_all_violations must not be invoked for same-side flips; got {len(calls)} call(s)"

    after = [(v.id, v.kind) for v in repo.all_violations() if v.ticker == "AAPL"]
    assert after == before, f"expected violations unchanged, got before={before} after={after}"

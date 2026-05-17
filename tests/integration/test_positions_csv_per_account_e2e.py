"""End-to-end: per-account positions CSV upload → verify run → annotated findings.

Proves that the Schwab per-account All-Positions CSV path:

1. Parses through ``POST /imports/positions``
2. Writes ``broker_position`` rows tied to the per-account label
3. Reconciles against our aggregated open lots via ``run_verify_once``
4. Produces a ``BasisRecon`` finding annotated with ``expected_section_1256``
   when the underlying is a §1256 contract opened in a prior calendar year

The §1256 carve-out is the cleanest annotation story to assert end-to-end:
Schwab applies §1256(a)(1) mark-to-market at year end while our open-lot basis
stays at original cost — the divergence is expected, not a real failure, and
the muted "expected" badge is what the user should see in the verify panel.

Unit-level coverage of the annotation helpers lives in
``tests/verify/test_broker_recon_annotations.py`` — this test closes the
ingestion → recon → persisted-finding loop with no mocks.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app

# Match the conftest pattern: skip scheduler startup in tests so
# AsyncIOScheduler doesn't try to bind to a missing event loop.
os.environ.setdefault("NETALPHA_SKIP_SCHEDULER", "1")

# Per-account fixture whose CSV header encodes the account as
# ``schwab/Demo999`` — this matches the ``broker/label`` display string
# our seeded SPX lot will surface as, so the recon pair-up actually
# matches and we hit BasisRecon (rather than PositionsMissing*).
FIXTURE = Path(__file__).parent.parent / "fixtures" / "positions" / "per_account_section_1256_recon.csv"

# Account display = ``schwab/Demo999``. Schwab's per-account export
# stuffs the broker-given nickname into the header; we mirror it here.
BROKER = "schwab"
LABEL = "Demo999"
ACCOUNT_DISPLAY = f"{BROKER}/{LABEL}"


@pytest.fixture
def client(tmp_path: Path) -> tuple[TestClient, Repository]:
    """Fresh isolated app + repo backed by a temp SQLite file."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    app = create_app(settings)
    test_client = TestClient(app, raise_server_exceptions=False)
    repo = Repository(engine)
    return test_client, repo


def _seed_spx_lot_prior_year(repo: Repository) -> None:
    """Seed one SPX buy in 2025 so the snapshot date (2026-05-16) is in a
    strictly later calendar year — the precondition for the §1256
    year-end-MTM annotation.

    Cost basis $4,500 deliberately disagrees with the fixture's $5,000 by
    well above the default $1.00 basis tolerance so BasisRecon fires.
    Quantity matches exactly (40) so no PositionsQty finding muddies the
    assertion.
    """
    account = repo.get_or_create_account(BROKER, LABEL)
    trade = Trade(
        date=date(2025, 12, 15),
        account=account.display(),
        ticker="SPX",
        action="Buy",
        quantity=40,
        proceeds=None,
        cost_basis=4500.0,
        basis_source="broker_csv",
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="seed_spx.csv",
        csv_sha256="sha-seed-spx",
        imported_at=datetime.now(),
        trade_count=1,
    )
    repo.add_import(account, record, [trade])
    # Materialize the LotRow(s). add_import only writes TradeRow; lots are
    # built by the wash-sale engine on recompute.
    recompute_all(repo)


def test_per_account_csv_upload_then_verify_emits_section_1256_annotation(client) -> None:
    """Upload per-account fixture → verify run → BasisRecon finding has
    ``expected_section_1256=True`` in detail_json.
    """
    test_client, repo = client

    # --- Seed: open SPX lot from prior year (2025-12-15) ---
    _seed_spx_lot_prior_year(repo)

    # Sanity: the lot exists with the expected account display string.
    lots = [lot for lot in repo.all_lots() if lot.ticker == "SPX"]
    assert len(lots) == 1, f"expected exactly one SPX lot, got {lots!r}"
    assert lots[0].account == ACCOUNT_DISPLAY
    assert lots[0].adjusted_basis == pytest.approx(4500.0)

    # --- Upload the per-account positions CSV ---
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"
    with FIXTURE.open("rb") as fh:
        resp = test_client.post(
            "/imports/positions",
            files={"file": ("per_account_section_1256_recon.csv", fh, "text/csv")},
            follow_redirects=False,
        )
    assert resp.status_code in (200, 303), f"unexpected status: {resp.status_code} body={resp.text[:300]}"

    # Sanity: broker_position rows persisted with the per-account label.
    bp_rows, as_of = repo.latest_broker_positions()
    assert as_of == "2026-05-16"
    assert any(bp.symbol == "SPX" and bp.account_label == ACCOUNT_DISPLAY for bp in bp_rows), (
        f"SPX broker_position row not found / wrong account_label: {[(b.symbol, b.account_label) for b in bp_rows]!r}"
    )

    # --- Trigger a deterministic verify run (today pinned so the
    #     reference-age math doesn't drift with the wall clock).
    from net_alpha.service.jobs.verify import run_verify_once

    out = run_verify_once(repo=repo, trigger="manual", today=date(2026, 5, 16))
    assert out["verify_result_id"] is not None

    # --- Inspect the latest verify run + its findings ---
    latest = repo.latest_verify_run()
    assert latest is not None
    findings = repo.list_verify_findings(run_id=latest.id)
    basis = [f for f in findings if f.rule_id == "BasisRecon" and "SPX" in f.scope]
    assert len(basis) >= 1, f"no SPX BasisRecon finding emitted (got rule_ids={[f.rule_id for f in findings]!r})"
    detail = json.loads(basis[0].detail_json or "{}")
    assert detail.get("expected_section_1256") is True, f"detail_json missing expected_section_1256=True: {detail!r}"

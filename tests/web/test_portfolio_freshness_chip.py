"""The Overview toolbar freshness chip must reflect the actual price-cache
state. A per-request PricingService starts with an empty snapshot, so the
'/' handler has to warm it from the cache before reading freshness —
otherwise the chip always reads 'none yet' even when fresh quotes exist."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.provider import Quote


def _seed_held_lot_with_fresh_quote(builders, repo, engine):
    """A held AAPL lot plus a freshly-cached quote — the warm-cache path."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date.today() - dt.timedelta(days=400), qty=10, cost=1000)],
    )
    for account in repo.list_accounts():
        stitch_account(repo, account.id)
    recompute_all_violations(repo, load_etf_pairs(user_path=None))
    PriceCache(engine).put_many(
        [Quote(symbol="AAPL", price=Decimal("200.00"), as_of=datetime.now(dt.UTC), source="test")]
    )


def test_overview_freshness_chip_reads_warm_cache_not_none_yet(client: TestClient, builders, repo, engine):
    _seed_held_lot_with_fresh_quote(builders, repo, engine)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # Fresh cached quotes must not be reported as "none yet".
    assert "Prices none yet" not in body
    # The green/fresh label format is "✓ {N}m" — rendered as "Prices ✓ ...".
    assert "Prices ✓" in body

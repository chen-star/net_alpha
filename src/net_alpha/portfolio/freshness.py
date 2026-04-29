"""Price freshness helper — compute a freshness tier and display label from a
PricingSnapshot.

Spec §5.11:
  < 15 min  →  green  / "✓ {N}m"
  15min–24h →  amber  / "⚠ {N}h"
  > 24h     →  red    / "✕ stale"
  no data   →  None   / "—"

Used by the toolbar freshness chip (Phase 3 B3) and reusable for Positions /
Tax pages in Phase 4.
"""

from __future__ import annotations

import datetime as dt


def compute_price_freshness(snapshot) -> tuple[str | None, str]:
    """Return (tier, label) from a PricingSnapshot.

    tier is one of 'green', 'amber', 'red', or None (no price data at all).
    label is a short human-readable string for display in the chip.
    """
    if snapshot is None:
        return None, "—"

    # degraded = provider failed; no fresh quotes are available.
    if getattr(snapshot, "degraded", False):
        return "red", "✕ stale"

    # fetched_at is set when at least one symbol was fetched fresh this request.
    fetched_at = getattr(snapshot, "fetched_at", None)

    # stale_symbols = symbols served from cache past the TTL (>15 min in cache).
    stale_symbols = getattr(snapshot, "stale_symbols", [])

    # missing_symbols = symbols with no price at all.
    missing_symbols = getattr(snapshot, "missing_symbols", [])

    # No quotes served at all (no open positions, or pricing disabled).
    if fetched_at is None and not stale_symbols and not missing_symbols:
        return None, "—"

    # If there are any stale symbols (served from >15-min-old cache), report amber/red.
    if stale_symbols:
        # We don't have the per-symbol age here; report amber as a conservative estimate.
        return "amber", "⚠ cached"

    if fetched_at is None:
        # Only missing symbols — no prices at all.
        return "red", "✕ stale"

    # Compute age of the most recent fetch.
    now = dt.datetime.now(dt.UTC)
    # fetched_at may be naive or aware; normalise to UTC-aware.
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=dt.UTC)
    age_seconds = (now - fetched_at).total_seconds()

    if age_seconds < 15 * 60:
        minutes = max(1, int(age_seconds // 60))
        return "green", f"✓ {minutes}m"
    elif age_seconds < 24 * 3600:
        hours = max(1, int(age_seconds // 3600))
        return "amber", f"⚠ {hours}h"
    else:
        return "red", "✕ stale"

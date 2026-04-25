from __future__ import annotations

from net_alpha.models.domain import Trade


def filter_new(trades: list[Trade], known_natural_keys: set[str]) -> list[Trade]:
    """Return only trades whose natural key is not in known_natural_keys."""
    return [t for t in trades if t.compute_natural_key() not in known_natural_keys]

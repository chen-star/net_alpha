from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

_BUNDLED_PATH = Path(__file__).resolve().parent.parent.parent.parent / "etf_pairs.yaml"


def load_etf_pairs(
    user_pairs_path: Optional[Path] = None,
) -> dict[str, list[str]]:
    """Load ETF substantially-identical pairs from bundled YAML + optional user overrides.

    User pairs extend defaults — they never replace them.
    """
    # Load bundled pairs
    with open(_BUNDLED_PATH) as f:
        pairs: dict[str, list[str]] = yaml.safe_load(f) or {}

    # Merge user pairs if file exists
    if user_pairs_path and user_pairs_path.exists():
        with open(user_pairs_path) as f:
            user_pairs: dict[str, list[str]] = yaml.safe_load(f) or {}
        for group, tickers in user_pairs.items():
            if group in pairs:
                # Extend, deduplicate
                existing = set(pairs[group])
                for ticker in tickers:
                    if ticker not in existing:
                        pairs[group].append(ticker)
            else:
                pairs[group] = tickers

    return pairs

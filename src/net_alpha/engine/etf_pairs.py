# src/net_alpha/engine/etf_pairs.py
from __future__ import annotations

import importlib.resources as resources
from pathlib import Path

import yaml


def load_etf_pairs(user_path: str | Path | None = None) -> dict[str, list[str]]:
    """Load bundled ETF substantially-identical pairs, optionally extended with user pairs.

    The bundled file ships inside the package at ``net_alpha/etf_pairs.yaml``.
    If *user_path* is supplied AND exists, its groups extend (do not replace) the
    bundled groups.  User pairs that share a group key with bundled pairs are
    deduplicated; new group keys are added wholesale.
    """
    bundled_text = resources.files("net_alpha").joinpath("etf_pairs.yaml").read_text()
    pairs: dict[str, list[str]] = yaml.safe_load(bundled_text) or {}

    if user_path:
        p = Path(user_path)
        if p.exists():
            user: dict[str, list[str]] = yaml.safe_load(p.read_text()) or {}
            for group, tickers in user.items():
                if group in pairs:
                    existing = set(pairs[group])
                    for ticker in tickers:
                        if ticker not in existing:
                            pairs[group].append(ticker)
                else:
                    pairs[group] = list(tickers)

    return pairs

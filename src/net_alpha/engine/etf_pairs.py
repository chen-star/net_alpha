# src/net_alpha/engine/etf_pairs.py
from __future__ import annotations

import importlib.resources as resources
import warnings
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


class ReplacementsConflictWarning(UserWarning):
    """Raised when a replacement appears in the source's substantially-identical pairs."""


def load_etf_replacements(
    user_path: str | Path | None = None,
    etf_pairs: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Load bundled ETF replacement suggestions, optionally extended with user file.

    If *etf_pairs* is provided, validate that no replacement appears in the source
    symbol's pair list; conflicts emit a warning and are excluded (fail-soft).
    """
    bundled_text = resources.files("net_alpha").joinpath("etf_replacements.yaml").read_text()
    repls: dict[str, list[str]] = yaml.safe_load(bundled_text) or {}

    if user_path:
        p = Path(user_path)
        if p.exists():
            user: dict[str, list[str]] = yaml.safe_load(p.read_text()) or {}
            for source, tickers in user.items():
                existing = set(repls.get(source, []))
                for ticker in tickers:
                    if ticker not in existing:
                        repls.setdefault(source, []).append(ticker)
                        existing.add(ticker)

    if etf_pairs:
        # For each source symbol in repls, find the etf_pairs group containing it
        # and exclude any replacement that's in the same group.
        for source, replacements in list(repls.items()):
            forbidden: set[str] = set()
            for group_members in etf_pairs.values():
                if source in group_members:
                    forbidden.update(group_members)
            kept = [r for r in replacements if r not in forbidden]
            dropped = set(replacements) - set(kept)
            if dropped:
                warnings.warn(
                    f"etf_replacements.yaml: {source} has conflicting replacements "
                    f"{sorted(dropped)} (also in etf_pairs.yaml); dropped.",
                    ReplacementsConflictWarning,
                    stacklevel=2,
                )
            repls[source] = kept

    return repls

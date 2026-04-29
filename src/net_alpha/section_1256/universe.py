"""§1256 universe loader + per-trade detection.

Mirrors the load pattern in net_alpha.engine.etf_pairs.load_etf_pairs:
bundled YAML inside the package, optional user override that *adds*
to (never replaces) the bundled list.
"""
from __future__ import annotations

import hashlib
import importlib.resources as resources
from pathlib import Path

import yaml

from net_alpha.models.domain import Trade


def _read_bundled() -> str:
    return resources.files("net_alpha").joinpath("section_1256_underlyings.yaml").read_text()


def _read_user(user_path: str | Path | None) -> str:
    if user_path is None:
        return ""
    p = Path(user_path)
    if not p.exists():
        return ""
    return p.read_text()


def load_universe(user_path: str | Path | None = None) -> set[str]:
    """Return the merged set of §1256 underlyings (bundled ∪ user override)."""
    bundled: dict[str, list[str]] = yaml.safe_load(_read_bundled()) or {}
    syms: set[str] = set(bundled.get("broad_based_index_options", []))

    user_text = _read_user(user_path)
    if user_text:
        user: dict[str, list[str]] = yaml.safe_load(user_text) or {}
        syms.update(user.get("broad_based_index_options", []))

    return syms


def is_section_1256(trade: Trade, *, user_path: str | Path | None = None) -> bool:
    """True iff *trade* is an option whose underlying is in the §1256 universe.

    Returns False for stock trades on the same ticker — §1256 applies only to
    listed option/futures contracts, not spot equity. SPX has no spot stock but
    the guard belongs in this function for safety.
    """
    if trade.option_details is None:
        return False
    return trade.ticker in load_universe(user_path=user_path)


def universe_hash(user_path: str | Path | None = None) -> str:
    """sha256 of the merged YAML content. Used to invalidate cached recompute state."""
    h = hashlib.sha256()
    h.update(_read_bundled().encode("utf-8"))
    user_text = _read_user(user_path)
    if user_text:
        h.update(b"\x00")
        h.update(user_text.encode("utf-8"))
    return h.hexdigest()

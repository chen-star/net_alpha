"""Tag normalization for position targets.

Single chokepoint: every tag string entering the system passes through
``normalize_tag``. Routes translate a None return into a 422; the bulk
helper ``normalize_tags`` silently drops invalid items because callers
pre-validate the individual values.
"""

from __future__ import annotations

import re
from typing import Iterable

# Reserved word: the synthetic bucket for targets with no tags. Cannot be
# used as a real tag.
RESERVED_TAGS: frozenset[str] = frozenset({"untagged"})

_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_tag(raw: str) -> str | None:
    """Return the normalized tag or None if invalid.

    Rules: trim, lowercase, collapse internal whitespace to '-',
    1–24 chars from [a-z0-9_-] with a leading alphanumeric, not reserved.
    """
    if not isinstance(raw, str):
        return None
    candidate = _WHITESPACE_RE.sub("-", raw.strip().lower())
    if not candidate:
        return None
    if candidate in RESERVED_TAGS:
        return None
    if not _TAG_RE.match(candidate):
        return None
    return candidate


def normalize_tags(raw: Iterable[str]) -> tuple[str, ...]:
    """Normalize, dedupe, and alpha-sort a sequence of tags.

    Invalid items are silently dropped — callers needing per-item
    validation should call ``normalize_tag`` directly.
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        norm = normalize_tag(item)
        if norm is None or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    out.sort()
    return tuple(out)

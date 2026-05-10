"""Lightweight check that table-bearing templates carry sticky-header
classes. Catches accidental removal of the sticky utility during future
template churn without needing a browser to verify scroll behavior.

Approach: parse each <thead>'s class attribute into a token set and
assert {"sticky", "top-0"} is a subset. This is order-independent and
immune to false positives from `sticky` appearing in non-class attributes
(e.g., title="…").

Templates excluded from the original plan list (verified to have no
<thead> at all):
- _tax_wash_sales_tab.html (delegates to _detail_table.html, which IS covered)
- _portfolio_wash_watch.html (CSS grid layout, no <table>)
- _ticker_view_reconciliation.html (HTMX wrapper for _reconciliation_diff.html, which IS covered)
- _imports_detail_row.html (a <td> fragment, no table)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Anchor to the project root so the test is invocation-directory-independent.
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src/net_alpha/web/templates"

# Templates whose <thead> rows must carry sticky-header classes.
STICKY_HEADER_TEMPLATES = [
    "_lots_table.html",
    "_ticker_view_timeline.html",
    "_ticker_view_lots.html",
    "_imports_table.html",
    "_detail_table.html",
    "_reconciliation_diff.html",
]

REQUIRED_TOKENS = frozenset({"sticky", "top-0"})

_THEAD_OPEN_RE = re.compile(r"<thead\b[^>]*>", re.DOTALL)
_CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')


def _thead_class_tokens(thead_tag: str) -> set[str]:
    """Return the set of class tokens on a <thead> opening tag, or an empty
    set if the tag has no class attribute."""
    m = _CLASS_ATTR_RE.search(thead_tag)
    if not m:
        return set()
    return set(m.group(1).split())


@pytest.mark.parametrize("template_name", STICKY_HEADER_TEMPLATES)
def test_template_has_at_least_one_sticky_thead(template_name: str) -> None:
    """At least one <thead> in each listed template carries sticky+top-0."""
    src = (TEMPLATES_DIR / template_name).read_text()
    found = False
    for m in _THEAD_OPEN_RE.finditer(src):
        if REQUIRED_TOKENS.issubset(_thead_class_tokens(m.group(0))):
            found = True
            break
    assert found, (
        f"{template_name}: no <thead> carries both 'sticky' and 'top-0' "
        "as class tokens; the table either lacks a <thead> wrapper or the "
        "sticky utility was removed."
    )


@pytest.mark.parametrize("template_name", STICKY_HEADER_TEMPLATES)
def test_every_thead_in_template_is_sticky(template_name: str) -> None:
    """Every <thead> in each listed template must be sticky.

    Some templates (e.g. _detail_table.html) have multiple <thead>s — one
    each for the wash-sales and exempt-matches tables. Each one must carry
    sticky+top-0; partial coverage is a regression."""
    src = (TEMPLATES_DIR / template_name).read_text()
    for m in _THEAD_OPEN_RE.finditer(src):
        tokens = _thead_class_tokens(m.group(0))
        missing = REQUIRED_TOKENS - tokens
        assert not missing, (
            f"{template_name}: <thead> at offset {m.start()} is missing "
            f"class tokens {sorted(missing)}; saw class tokens {sorted(tokens)}."
        )

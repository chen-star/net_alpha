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


# --- Sticky-left first column ---

STICKY_LEFT_TEMPLATES = [
    "_lots_table.html",
    "_detail_table.html",
    "_ticker_view_timeline.html",
    "_ticker_view_lots.html",
]

REQUIRED_LEFT_TOKENS = frozenset({"sticky", "left-0"})

# Match any opening tag of <th>, <td>, etc. with optional attributes. We only
# need the first cell per row, but a presence check on at least one sticky-left
# cell is sufficient for the smoke test — Jinja loops mean we cannot easily
# count cells per row from raw template source without parsing Jinja control flow.
_CELL_OPEN_RE = re.compile(r"<(?:th|td)\b[^>]*>", re.DOTALL)


def _cell_class_tokens(cell_tag: str) -> set[str]:
    m = _CLASS_ATTR_RE.search(cell_tag)
    if not m:
        return set()
    return set(m.group(1).split())


@pytest.mark.parametrize("template_name", STICKY_LEFT_TEMPLATES)
def test_template_has_at_least_one_sticky_left_cell(template_name: str) -> None:
    """At least one <th>/<td> in each listed template carries sticky+left-0
    as class tokens. Catches accidental removal of the sticky-left utility."""
    src = (TEMPLATES_DIR / template_name).read_text()
    for m in _CELL_OPEN_RE.finditer(src):
        if REQUIRED_LEFT_TOKENS.issubset(_cell_class_tokens(m.group(0))):
            return
    pytest.fail(
        f"{template_name}: no <th>/<td> carries both 'sticky' and 'left-0' "
        "as class tokens; horizontal scroll will not anchor the first column."
    )


def test_timeline_thead_has_layered_sticky_left() -> None:
    """The timeline table needs both the rail-col AND the Date column
    sticky-left, layered with the Date column offset by the rail width.
    Rail-col anchors pair-line connectors; Date anchors row identity."""
    src = (TEMPLATES_DIR / "_ticker_view_timeline.html").read_text()
    sticky_left_thead_cells = 0
    in_thead = False
    for line in src.splitlines():
        if "<thead" in line:
            in_thead = True
        if "</thead>" in line:
            in_thead = False
        if in_thead and "<th" in line:
            # crude per-line scan; a <th> opening can span multiple lines but
            # the class attribute is typically inline
            tag_open = line[line.find("<th") :]
            tokens = _cell_class_tokens(tag_open)
            if (
                {"sticky", "left-0"}.issubset(tokens)
                or any(t.startswith("left-[") for t in tokens)
                and "sticky" in tokens
            ):
                sticky_left_thead_cells += 1
    assert sticky_left_thead_cells >= 2, (
        f"_ticker_view_timeline.html: expected at least 2 sticky-left "
        f"<th> cells in <thead> (rail-col + Date); found {sticky_left_thead_cells}."
    )

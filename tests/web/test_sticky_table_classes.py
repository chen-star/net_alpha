"""Lightweight regex check that table-bearing templates carry sticky-header
classes. This catches accidental removal of the sticky utility during future
template churn without needing a browser to verify scroll behavior.

Templates originally listed in the plan that do NOT contain a <thead> element
and were therefore excluded from this check (they are fragments or use
non-table layout):

- _tax_wash_sales_tab.html: no <table>; delegates rendering to
  _detail_table.html and _portfolio_wash_watch.html via {% include %}.
- _portfolio_wash_watch.html: no <table>; renders a CSS grid/flexbox layout.
- _ticker_view_reconciliation.html: no <table>; loads reconciliation data via
  HTMX GET into child divs; the actual table lives in a route-rendered partial.
- _imports_detail_row.html: a <td> fragment (detail expand panel); contains
  no table element at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES_DIR = Path("src/net_alpha/web/templates")

# Templates whose <thead> rows must carry sticky-header classes.
# Note: four templates from the original plan were removed because they contain
# no <thead> element (see module docstring above).
STICKY_HEADER_TEMPLATES = [
    "_lots_table.html",
    "_ticker_view_timeline.html",
    "_ticker_view_lots.html",
    "_imports_table.html",
]

STICKY_HEADER_PATTERN = re.compile(
    r"<thead[^>]*class=\"[^\"]*\bsticky\b[^\"]*\btop-0\b[^\"]*\"",
    re.DOTALL,
)


@pytest.mark.parametrize("template_name", STICKY_HEADER_TEMPLATES)
def test_template_has_sticky_thead(template_name: str) -> None:
    src = (TEMPLATES_DIR / template_name).read_text()
    assert STICKY_HEADER_PATTERN.search(src), (
        f"{template_name}: <thead> must carry 'sticky top-0' classes; "
        "the table either lacks a <thead> wrapper or the sticky utility "
        "was removed."
    )

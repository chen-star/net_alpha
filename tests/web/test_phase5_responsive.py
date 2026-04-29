"""Phase 5 — smoke tests at tablet width (768px).

Asserts every page returns 200 OK; the tablet snapshot suite catches
visual regressions, this test catches outright server errors triggered
by responsive class changes.
"""

from __future__ import annotations

import pytest

PAGES = [
    "/",
    "/positions?view=all",
    "/positions?view=stocks",
    "/positions?view=options",
    "/positions?view=at-loss",
    "/positions?view=closed",
    "/tax?view=wash-sales",
    "/tax?view=projection",
    "/settings/imports",
    "/sim",
]


@pytest.mark.parametrize("path", PAGES)
def test_page_returns_200(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code}"
    # Sanity — desktop-only banner is present in markup (always; CSS hides
    # it above md). If the banner string is missing, base.html change was
    # reverted.
    assert "desktop-first" in r.text.lower()

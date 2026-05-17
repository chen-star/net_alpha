"""E2E: equity-curve click-to-explain smoke.

Asserts the click → htmx → explain-panel wiring end-to-end. The Phase-3
template + Phase-4 click wiring are tested in isolation elsewhere; this
smoke covers the real-browser path: ApexCharts must render a marker, the
``dataPointSelection`` event must fire on click, the route response must
swap into ``#explain-equity-point``, and the swapped fragment must carry
the ``data-explain="equity-point"`` marker.

Uses the shared ``live_server_seeded`` fixture from ``conftest.py`` which
boots the demo DB (two accounts: schwab/taxable + schwab/ira).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


def _suppress_overlays(page: Page) -> None:
    """Same overlay-defuser used by other e2e tests.

    The ⌘K palette overlay can fail to initialize cleanly in headless
    Chromium and leaves its backdrop intercepting pointer events.
    """
    page.evaluate(
        """
        () => {
            document.querySelectorAll('[role="dialog"][aria-label="Command palette"]').forEach(el => {
                el.style.display = 'none';
            });
            document.querySelectorAll('dialog[open]').forEach(d => d.close());
        }
        """
    )


@pytest.mark.e2e
def test_equity_curve_click_swaps_explain_panel(page: Page, live_server_seeded: str) -> None:
    """Click a marker on the equity-curve chart and assert the explain
    panel (``data-explain="equity-point"``) is rendered into the mount
    div within a short timeout."""
    page.goto(f"{live_server_seeded}/", wait_until="networkidle", timeout=15_000)
    _suppress_overlays(page)

    # Wait for ApexCharts to finish rendering markers on the equity-value
    # series. The chart has two series (Contributions line + Account value
    # area); markers appear on both. Any one marker is enough.
    page.wait_for_selector("#equity-chart .apexcharts-marker", timeout=10_000)

    markers = page.locator("#equity-chart .apexcharts-marker")
    count = markers.count()
    if count < 1:
        pytest.skip(f"demo DB did not render any equity-curve markers (got {count})")

    # Click a marker roughly in the middle of the series — the demo dataset
    # is contiguous so any interior marker should yield a valid delta.
    # `force=True` is needed because ApexCharts overlays the SVG marker
    # with a transparent rect that Playwright may consider the topmost
    # element at the same coords.
    target_idx = min(count - 1, max(1, count // 2))
    markers.nth(target_idx).click(force=True)

    # The click wires through ApexCharts dataPointSelection → htmx.ajax
    # GET /portfolio/explain/equity-point → innerHTML swap into
    # #explain-equity-point. Wait for the explain marker to appear.
    page.wait_for_selector(
        '#explain-equity-point [data-explain="equity-point"]',
        timeout=5_000,
    )

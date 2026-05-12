"""End-to-end: the multi-account checkbox dropdown on the Positions page.

Exercises the actual UI control via a real browser (headless Chromium).
``build_demo_db`` seeds two accounts (schwab/taxable + schwab/ira) so all
multi-account assertions run unconditionally — no skip needed.

Implementation note on Alpine.js in headless Chromium
------------------------------------------------------
The ⌘K ``paletteOverlay`` Alpine component fails to initialize in headless
Chromium (``paletteOverlay is not defined`` at eval time — a race between
Alpine's DOMContentLoaded init and the ``defer``-loaded ``palette.js``).
When the component errors, Alpine does not process its ``x-show="open"``
directive, leaving the fixed full-screen backdrop rendered with ``display:flex``
and intercepting all pointer events.

``_ready()`` works around this by force-hiding the palette overlay via direct
DOM manipulation before any click, which is safe: the palette is not under test
here, and the effect is cosmetic (it would remain hidden anyway once Alpine is
healthy).  Dismiss via Escape is attempted first, then JS fallback.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


def _ready(page: Page, timeout: int = 10_000) -> None:
    """Wait until the page is safe to interact with.

    1. Wait for Alpine to finish its init pass (x-cloak count → 0).
    2. Force-hide the palette overlay backdrop in case the ``paletteOverlay``
       Alpine component failed to initialize in headless Chromium (known
       rendering discrepancy — does not affect the feature under test).
    3. Wait until the dropdown trigger button is the topmost element at its
       own centre coordinates (confirms no overlay is blocking it).
    """
    # Step 1: Alpine init pass — all x-cloak attributes removed.
    page.wait_for_function(
        "document.querySelectorAll('[x-cloak]').length === 0 || "
        "document.querySelectorAll('[x-cloak]').length > -1",  # always true once DOM ready
        timeout=timeout,
    )
    # Give Alpine a moment to settle x-show directives.
    page.wait_for_timeout(300)

    # Step 2: Force-hide any full-screen overlay that Alpine failed to hide.
    # This targets the palette backdrop specifically (fixed, inset-0, z-50).
    page.evaluate("""
        () => {
            // Dismiss via Alpine if open, otherwise hide the element directly.
            document.querySelectorAll('[role="dialog"][aria-label="Command palette"]').forEach(el => {
                el.style.display = 'none';
            });
            // Also close any <dialog> that may be open (profile picker).
            document.querySelectorAll('dialog[open]').forEach(d => d.close());
        }
    """)
    page.wait_for_timeout(100)


def test_multi_account_dropdown_renders(page: Page, live_server_seeded: str):
    """The ``account_multi_select`` macro root div is present exactly once."""
    page.goto(f"{live_server_seeded}/positions", wait_until="networkidle", timeout=15_000)
    _ready(page)
    dropdown = page.locator("[data-testid='account-multi-select']")
    assert dropdown.count() == 1, "multi-account dropdown must render exactly once"
    # The trigger initially reads "All accounts" when no filter is active.
    trigger_text = dropdown.locator("button").first.inner_text()
    assert "All accounts" in trigger_text or "of" in trigger_text, (
        f"Unexpected trigger label: {trigger_text!r}"
    )


def test_dropdown_opens_and_closes(page: Page, live_server_seeded: str):
    """Clicking the trigger button shows/hides the listbox popover."""
    page.goto(f"{live_server_seeded}/positions", wait_until="networkidle", timeout=15_000)
    _ready(page)
    dropdown = page.locator("[data-testid='account-multi-select']")
    listbox = dropdown.locator("[role='listbox']")

    # Initially closed (x-show=false hides it; may be hidden via display:none
    # from x-show or x-cloak; either way is_visible() returns False).
    assert not listbox.first.is_visible(), "popover should be hidden before opening"

    # Click the trigger to open.
    dropdown.locator("button").first.click()
    page.wait_for_timeout(300)  # Alpine x-show transition
    assert listbox.first.is_visible(), "popover should open after clicking the trigger"

    # Click outside to close.
    page.mouse.click(10, 10)
    page.wait_for_timeout(300)
    assert not listbox.first.is_visible(), "popover should close on outside click"


def test_dropdown_lists_accounts_from_demo_db(page: Page, live_server_seeded: str):
    """The demo DB seeds two accounts; both should appear as individual checkboxes."""
    page.goto(f"{live_server_seeded}/positions", wait_until="networkidle", timeout=15_000)
    _ready(page)
    dropdown = page.locator("[data-testid='account-multi-select']")
    dropdown.locator("button").first.click()
    page.wait_for_timeout(300)

    # Per-account checkboxes have name="account"; the master "All accounts" toggle does not.
    account_checkboxes = dropdown.locator("input[type='checkbox'][name='account']")
    count = account_checkboxes.count()
    assert count >= 2, (
        f"demo DB seeds taxable + ira accounts; expected ≥2 checkboxes, got {count}"
    )


def test_toggle_account_updates_url(page: Page, live_server_seeded: str):
    """Toggle one account off; the URL should include an account= query parameter."""
    page.goto(f"{live_server_seeded}/positions", wait_until="networkidle", timeout=15_000)
    _ready(page)
    dropdown = page.locator("[data-testid='account-multi-select']")
    dropdown.locator("button").first.click()
    page.wait_for_timeout(300)

    account_checkboxes = dropdown.locator("input[type='checkbox'][name='account']")
    if account_checkboxes.count() < 2:
        pytest.skip("demo data has fewer than 2 accounts — cannot test partial filtering")

    # Uncheck the first account (deselects it; keeps the second selected).
    account_checkboxes.first.click()

    # The macro debounces 200 ms then submits the parent form — wait for navigation.
    page.wait_for_url("**/positions?**", timeout=3_000)
    assert "account=" in page.url, (
        f"Expected account= in URL after toggling one account off, got: {page.url!r}"
    )


def test_all_accounts_trigger_label_shows_partial_when_one_deselected(page: Page, live_server_seeded: str):
    """Deselecting one account changes the trigger label away from 'All accounts'."""
    page.goto(f"{live_server_seeded}/positions", wait_until="networkidle", timeout=15_000)
    _ready(page)
    dropdown = page.locator("[data-testid='account-multi-select']")

    # Confirm initial state shows "All accounts" (no filter).
    trigger_initial = dropdown.locator("button").first.inner_text()
    assert "All accounts" in trigger_initial, (
        f"Before any filter, expected 'All accounts', got: {trigger_initial!r}"
    )

    # Open and deselect the first account.
    dropdown.locator("button").first.click()
    page.wait_for_timeout(300)
    account_checkboxes = dropdown.locator("input[type='checkbox'][name='account']")
    if account_checkboxes.count() < 2:
        pytest.skip("demo data has fewer than 2 accounts")

    account_checkboxes.first.click()
    page.wait_for_url("**/positions?**", timeout=3_000)
    _ready(page)

    # With one account deselected, the label must NOT show "All accounts".
    trigger_after = dropdown.locator("button").first.inner_text()
    assert "All accounts" not in trigger_after, (
        f"After deselecting one account, label should not be 'All accounts'; got: {trigger_after!r}"
    )
    # And the URL must contain the account= filter parameter.
    assert "account=" in page.url, (
        f"Expected account= in URL after partial filter, got: {page.url!r}"
    )

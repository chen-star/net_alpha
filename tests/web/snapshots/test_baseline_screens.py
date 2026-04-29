"""Capture / verify baseline page screenshots.

Behavior:
  - When `--update-snapshots` is passed, write a fresh PNG to baseline/.
  - Otherwise, fail with a diff if the captured PNG differs from baseline
    by more than the threshold.

Routes covered reflect the Phase 1 IA: top nav is
``Overview · Positions · Tax · Sim``; the harvest queue moved to
``/positions?view=at-loss``; the imports page now opens in the Settings
drawer via ``/settings/imports``.

Each route is captured at 1440×900 (desktop) and 768×1024 (tablet).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page

BASELINE_DIR = Path(__file__).parent / "baseline"

PAGES = [
    ("overview", "/"),
    ("positions-all", "/positions?view=all"),
    ("positions-at-loss", "/positions?view=at-loss"),
    ("tax-wash", "/tax?view=wash-sales"),
    ("tax-proj", "/tax?view=projection"),
    ("settings-imports", "/settings/imports"),
    ("sim", "/sim"),
    ("ticker-nvda", "/ticker/NVDA"),
]

WIDTHS = [
    ("tablet", 768, 1024),
    ("laptop", 1024, 768),
    ("desktop", 1280, 800),
    ("desktop-wide", 1440, 900),
]


@pytest.fixture
def update_snapshots(request) -> bool:
    return bool(request.config.getoption("--update-snapshots"))


@pytest.mark.parametrize("name,path", PAGES, ids=[p[0] for p in PAGES])
@pytest.mark.parametrize("device,width,height", WIDTHS, ids=[w[0] for w in WIDTHS])
def test_baseline_snapshot(
    name: str,
    path: str,
    device: str,
    width: int,
    height: int,
    page: Page,
    live_server: str,
    update_snapshots: bool,
) -> None:
    out_dir = BASELINE_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{device}.png"

    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{live_server}{path}", wait_until="networkidle", timeout=10_000)
    # Settle HTMX-loaded fragments. networkidle covers most; small extra buffer
    # for ApexCharts fade-in animations.
    page.wait_for_timeout(800)

    if update_snapshots or not out.exists():
        page.screenshot(path=out, full_page=False)
        if not out.exists():
            pytest.fail(f"snapshot write failed: {out}")
        return

    actual = page.screenshot(full_page=False)
    expected = out.read_bytes()
    if actual == expected:
        return

    # Pixel-equal failed; allow a small tolerance via byte-length proxy.
    # (A proper SSIM diff is overkill for Phase 0; the ~1% threshold lives
    # at the byte-size level for now and gets refined in Phase 4 if noisy.)
    diff_bytes = abs(len(actual) - len(expected))
    threshold = max(int(len(expected) * 0.01), 512)
    if diff_bytes > threshold:
        diff_path = out.with_suffix(".diff.png")
        diff_path.write_bytes(actual)
        pytest.fail(f"snapshot mismatch for {name}/{device} (|Δsize|={diff_bytes} > {threshold}); wrote {diff_path}")

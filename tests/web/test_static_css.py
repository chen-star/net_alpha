"""Compiled-CSS regression net: every class name that templates use directly
must survive the Tailwind purge into `app.css`.

Templates referencing these classes:
- `_data_hygiene.html` → `.badge-error` (when issue.severity == 'error')
- `verify/index.html`, `verify/_findings_table.html` →
  `.status-pass/.status-fail/.status-warn/.status-error`
- `verify/index.html` → `.bg-warn-soft` (stale freshness banner)
- `welcome.html` → `.hover:border-accent` (welcome-card hover)
- `_imports_table.html` → `.border-confirmed-soft`
- `_lots_table.html` → `.bg-warn-soft-5`
- `_detail_table.html` → `.bg-warn-soft-10`, `.bg-info-soft-10`

Adding a new template class? Add it here too so Tailwind purging or a typo
won't ship a silently-broken UI.
"""

from pathlib import Path

import pytest

CSS_PATH = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "static" / "app.css"


@pytest.fixture(scope="module")
def compiled_css() -> str:
    return CSS_PATH.read_text()


@pytest.mark.parametrize(
    "selector",
    [
        # Task 3.1 — audit #22, #23, #24, #26
        ".badge-error",
        ".status-pass",
        ".status-fail",
        ".status-warn",
        ".status-error",
        ".bg-warn-soft",
        ".border-accent",
        r".hover\:border-accent:hover",
        # Task 3.2 — audit #25 (explicit-alpha replacements for Tailwind
        # `color/N` syntax that no-ops on CSS-variable colors).
        ".border-confirmed-soft",
        ".bg-warn-soft-5",
        ".bg-warn-soft-10",
        ".bg-info-soft-10",
        # Task 3.6 — audit #32 (neutral source decoration for the
        # `_violation_card.html` Cross-account chip).
        ".chip-source",
    ],
)
def test_template_class_ships_in_compiled_css(compiled_css: str, selector: str) -> None:
    assert selector in compiled_css, (
        f"Selector {selector!r} not in compiled app.css. "
        "If you renamed it in app.src.css, update this test; otherwise "
        "Tailwind likely purged it because no template references it."
    )

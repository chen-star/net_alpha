"""Settings drawer entry-point routes.

`/settings` and `/settings/imports` both render `base.html` with an
Alpine one-shot that opens the Settings drawer to a specific tab on
load. This makes deep-links into the drawer work — e.g. the Imports nav
badge link from prior versions of the app continues to land the user
exactly where they expect.

Phase 1 supports two entry points:
  - /settings           → opens drawer to default tab (imports)
  - /settings/imports   → opens drawer to imports tab

Phases 2-3 add: /settings/profile, /settings/density, /settings/etf-pairs,
/settings/about. Until then those URLs 404 — fine since nothing links to
them.

The page body underneath the drawer is intentionally minimal — when the
user closes the drawer they get a near-blank page with the topbar visible.
That's acceptable: users only land on `/settings/*` via the redirect from
`/imports`, and the drawer is the focus.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
@router.get("/settings/imports", response_class=HTMLResponse)
def settings_drawer_entry(request: Request) -> HTMLResponse:
    """Render `base.html` with `open_settings_tab` in the context.

    The drawer is mounted by `base.html`. The auto-open script in
    `base.html` reads `data-open-settings-tab="imports"` from the body
    on `alpine:init` and dispatches `open-settings-drawer`.
    """
    return request.app.state.templates.TemplateResponse(
        request,
        "base.html",
        {
            "active_page": "overview",
            "open_settings_tab": "imports",
        },
    )

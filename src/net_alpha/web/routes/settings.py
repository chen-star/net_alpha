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

Carryforward fragment (`/settings/carryforward`) renders the loss-carryforward
list section as an HTMX-loadable fragment. It lives here (not in a separate
file) so the entire Settings surface stays under one router.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.portfolio.carryforward import get_effective_carryforward
from net_alpha.web.dependencies import get_repository

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
        "settings_entry.html",
        {"open_settings_tab": "imports"},
    )


@router.get("/settings/carryforward", response_class=HTMLResponse)
def settings_carryforward(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """List per-year ST/LT carryforward state.

    One row per tax year from ``earliest_trade_year + 1`` through
    ``current_year + 1``, unioned with any years that already have a
    user override (so out-of-range overrides remain visible/editable).

    Each row reports the effective carryforward (override-wins via
    ``get_effective_carryforward``) along with its source: ``user``,
    ``derived``, or ``none``.
    """
    earliest = repo.earliest_trade_year()
    has_history = earliest is not None
    current_year = date.today().year

    years_to_show: set[int] = set()
    if has_history:
        years_to_show.update(range(earliest + 1, current_year + 2))
    for ov in repo.all_carryforward_overrides():
        years_to_show.add(ov.year)

    rows = []
    for year in sorted(years_to_show):
        cf = get_effective_carryforward(repo, year)
        rows.append(
            {
                "year": year,
                "st": cf.st,
                "lt": cf.lt,
                "source": cf.source,
            }
        )

    return request.app.state.templates.TemplateResponse(
        request,
        "_settings_carryforward.html",
        {"rows": rows, "has_history": has_history},
    )


@router.get("/settings/carryforward/edit", response_class=HTMLResponse)
def settings_carryforward_edit(
    request: Request,
    year: int,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """Render an inline edit-row form for a single carryforward year.

    Pre-fills with the currently effective ST/LT magnitudes (override or
    derived). The fragment swaps the original `<tr>` in the carryforward
    table; submitting POSTs to `/settings/carryforward/save` and re-renders
    the whole section.
    """
    cf = get_effective_carryforward(repo, year)
    return request.app.state.templates.TemplateResponse(
        request,
        "_settings_carryforward_edit_row.html",
        {"year": year, "st": cf.st, "lt": cf.lt},
    )


@router.post("/settings/carryforward/save", response_class=HTMLResponse)
def settings_carryforward_save(
    request: Request,
    year: int = Form(...),
    st_amount: str = Form(...),
    lt_amount: str = Form(...),
    note: str | None = Form(None),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """Upsert a user override for `year` and re-render the section.

    Amounts are stored as positive magnitudes; sign is flipped at apply-time
    inside the planner / after-tax math. Negative or non-numeric inputs are
    rejected with 422.
    """
    try:
        st = Decimal(st_amount)
        lt = Decimal(lt_amount)
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail="amounts must be numeric") from exc
    if st < 0 or lt < 0:
        raise HTTPException(status_code=422, detail="amounts must be non-negative")

    note_value = note.strip() if note and note.strip() else None
    repo.upsert_carryforward_override(year=year, st=st, lt=lt, note=note_value)
    return settings_carryforward(request, repo=repo)


@router.post("/settings/carryforward/reset", response_class=HTMLResponse)
def settings_carryforward_reset(
    request: Request,
    year: int,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """Delete the override for `year`, falling back to the derived value."""
    repo.delete_carryforward_override(year)
    return settings_carryforward(request, repo=repo)

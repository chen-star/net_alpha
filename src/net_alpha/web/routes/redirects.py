"""Phase 1 IA redirects.

Three permanent (301) redirects keep old URLs working after the §3 IA shift:
  - /holdings → /positions
  - /tax?view=harvest → /positions?view=at-loss
  - /imports → /settings/imports

Query strings are preserved on every redirect so per-page filters (period,
account) and feature flags (e.g. ``?wizard=1`` from the welcome flow) survive
the hop.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/holdings", include_in_schema=False)
def holdings_redirect(request: Request) -> RedirectResponse:
    target = "/positions"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=301)


@router.get("/imports", include_in_schema=False)
def imports_redirect(request: Request) -> RedirectResponse:
    target = "/settings/imports"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=301)

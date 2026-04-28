"""Phase 1 IA redirects.

Three permanent (301) redirects keep old URLs working after the §3 IA shift:
  - /holdings → /positions
  - /tax?view=harvest → /positions?view=at-loss
  - /imports → /settings/imports

Query-string preservation is explicit on /holdings since per-page filters
(period, account) are part of the URL and must survive the redirect.
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

"""Tour state-mutation endpoints. All redirect (303) on success."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository

router = APIRouter(prefix="/tour")


def _real_repo(request: Request) -> Repository:
    settings: Settings = request.app.state.settings
    return Repository(get_engine(settings.db_path))


def _strip_tour_query(referer: str) -> str:
    if not referer:
        return "/"
    parts = urlsplit(referer)
    if not parts.query:
        return parts.path or "/"
    kept = [p for p in parts.query.split("&") if not p.startswith("tour=")]
    new_query = "&".join(kept)
    return urlunsplit(("", "", parts.path or "/", new_query, ""))


@router.post("/dismiss")
def dismiss(request: Request) -> RedirectResponse:
    _real_repo(request).set_tour_completed(True)
    target = _strip_tour_query(request.headers.get("referer", ""))
    return RedirectResponse(target, status_code=303)


@router.post("/replay")
def replay(request: Request) -> RedirectResponse:
    _real_repo(request).set_tour_completed(False)
    request.app.state.demo_mode = True
    return RedirectResponse("/welcome?replay=1", status_code=303)


@router.post("/exit-to-real")
def exit_to_real(request: Request) -> RedirectResponse:
    request.app.state.demo_mode = False
    _real_repo(request).set_tour_completed(True)
    return RedirectResponse("/imports", status_code=303)

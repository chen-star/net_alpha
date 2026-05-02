"""POST /preferences — write per-account profile + density + theme.

Returns 204 + HX-Refresh: true so HTMX clients reload the current page.
Form params:
    account_id (optional, int)
    profile    (required, 'conservative' | 'active' | 'options')
    density    (required, 'compact' | 'comfortable' | 'tax')
    theme      (optional, 'system' | 'light' | 'dark', default 'system')

When account_id is omitted, the same prefs are written to every existing
account (the "all accounts" shortcut from the first-visit modal).

When `theme` is the only field changing, the toggle's inline JS already
flips `<html data-theme>` for instant feedback before this round-trip; the
HX-Refresh ensures the server-rendered FOUC script reads the right value
on the next navigation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Response

from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.dependencies import get_repository

router = APIRouter()

_VALID_PROFILES = {"conservative", "active", "options"}
_VALID_DENSITIES = {"compact", "comfortable", "tax"}
_VALID_THEMES = {"system", "light", "dark"}


@router.post("/preferences", status_code=204)
def post_preferences(
    profile: str = Form(...),
    density: str = Form(...),
    theme: str = Form(default="system"),
    account_id: int | None = Form(default=None),
    repo: Repository = Depends(get_repository),
) -> Response:
    if profile not in _VALID_PROFILES or density not in _VALID_DENSITIES:
        raise HTTPException(status_code=422, detail="invalid profile or density")
    if theme not in _VALID_THEMES:
        raise HTTPException(status_code=422, detail="invalid theme")

    accounts = repo.list_accounts()
    targets: list[int]
    if account_id is None:
        targets = [a.id for a in accounts]
    else:
        if not any(a.id == account_id for a in accounts):
            raise HTTPException(status_code=404, detail="account not found")
        targets = [account_id]

    now = datetime.now(UTC)
    for aid in targets:
        repo.upsert_user_preference(
            AccountPreference(
                account_id=aid,
                profile=profile,  # type: ignore[arg-type]
                density=density,  # type: ignore[arg-type]
                theme=theme,  # type: ignore[arg-type]
                updated_at=now,
            )
        )

    headers = {"HX-Refresh": "true"}
    return Response(status_code=204, headers=headers)

"""/settings/accounts — let the user classify each account label."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.accounts import AccountType
from net_alpha.web.dependencies import get_repository
from net_alpha.web.fragment_cache import bump_fragment_revision

router = APIRouter(prefix="/settings/accounts")

VALID_TYPES = {t.value for t in AccountType}


def _is_tax_advantaged(type_str: str) -> bool:
    """True for any IRA / Roth / 401(k) / HSA — these gate the
    Rev. Rul. 2008-5 IRA-trap classification.

    Wraps the enum's ``is_tax_advantaged`` so callers can pass the raw
    persisted string without round-tripping through AccountType themselves.
    """
    try:
        return AccountType(type_str).is_tax_advantaged
    except ValueError:
        return False


@router.get("", response_class=HTMLResponse)
async def list_accounts(request: Request, repo: Repository = Depends(get_repository)) -> HTMLResponse:
    """Render the account-type editor.

    Direct browser navigation gets the full base.html shell (nav + theme +
    footer); HTMX swaps get just the bare fragment so the swap target isn't
    nested under a second <html>/<body>.
    """
    rows = repo.list_accounts()
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    template = "_settings_accounts.html" if is_htmx else "settings_accounts.html"
    return request.app.state.templates.TemplateResponse(
        request,
        template,
        {
            "accounts": rows,
            "types": [t.value for t in AccountType],
        },
    )


@router.post("", response_class=HTMLResponse)
async def update_account(
    request: Request,
    broker: str = Form(...),
    label: str = Form(...),
    type: str = Form(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    if type not in VALID_TYPES:
        return HTMLResponse(f"invalid type: {type}", status_code=400)
    # Capture the old type before mutating so we can decide whether the flip
    # crosses the taxable ↔ tax-advantaged boundary that drives the §1091 /
    # Rev. Rul. 2008-5 IRA-trap classifier. A flip within the same side
    # (e.g. trad_ira → roth_ira) doesn't change wash-sale outcomes, so we
    # skip the recompute.
    old_type = repo.get_account_type(broker=broker, label=label)
    repo.set_account_type(broker=broker, label=label, type_=type)
    if _is_tax_advantaged(old_type) != _is_tax_advantaged(type):
        # Triggers reclassification of every existing WashSaleViolation.kind
        # (deferred ↔ permanent_ira) AND rebuilds lot.adjusted_basis so any
        # previously rolled-in §1091(d) basis adjustments are reversed for the
        # now-permanent_ira leg (and vice versa).
        recompute_all_violations(repo, load_etf_pairs())
    bump_fragment_revision(request)
    return await list_accounts(request, repo=repo)

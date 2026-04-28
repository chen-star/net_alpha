from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.models.domain import Trade
from net_alpha.web.dependencies import get_repository

router = APIRouter()


_ACTION_MAP = {
    "Buy": ("Buy", "user"),
    "Sell": ("Sell", "user"),
    "Transfer In": ("Buy", "transfer_in"),
    "Transfer Out": ("Sell", "transfer_out"),
}


def _validate_account(repo: Repository, account: str) -> None:
    """Reject accounts that don't already exist."""
    accounts = {f"{a.broker}/{a.label}" for a in repo.list_accounts()}
    if account not in accounts:
        raise HTTPException(status_code=400, detail=f"unknown account: {account!r}")


def _parse_date(raw: str) -> date:
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid date: {raw!r}") from None
    if d > date.today():
        raise HTTPException(status_code=400, detail="date must not be in the future")
    return d


@router.post("/trades", response_model=None)
def create_trade(
    request: Request,
    account: str = Form(...),
    ticker: str = Form(...),
    trade_date: str = Form(...),
    action_choice: str = Form(...),
    quantity: float = Form(...),
    basis_or_proceeds: float = Form(...),
    repo: Repository = Depends(get_repository),
) -> RedirectResponse:
    if action_choice not in _ACTION_MAP:
        raise HTTPException(status_code=400, detail=f"invalid action: {action_choice!r}")
    if not ticker.strip():
        raise HTTPException(status_code=400, detail="ticker required")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")
    if basis_or_proceeds < 0:
        raise HTTPException(status_code=400, detail="basis/proceeds must be >= 0")
    _validate_account(repo, account)
    d = _parse_date(trade_date)

    action, basis_source = _ACTION_MAP[action_choice]
    is_buy_side = action == "Buy"
    trade = Trade(
        account=account,
        date=d,
        ticker=ticker.strip().upper(),
        action=action,
        quantity=quantity,
        cost_basis=basis_or_proceeds if is_buy_side else None,
        proceeds=basis_or_proceeds if not is_buy_side else None,
        basis_source=basis_source,
        is_manual=True,
    )
    etf_pairs = load_etf_pairs()
    repo.create_manual_trade(trade, etf_pairs=etf_pairs)
    response = RedirectResponse(url=f"/ticker/{trade.ticker}", status_code=303)
    response.headers["HX-Redirect"] = f"/ticker/{trade.ticker}"
    return response


@router.post("/trades/{trade_id}/edit-manual", response_model=None)
def edit_manual(
    request: Request,
    trade_id: str,
    account: str = Form(...),
    ticker: str = Form(...),
    trade_date: str = Form(...),
    action_choice: str = Form(...),
    quantity: float = Form(...),
    basis_or_proceeds: float = Form(...),
    repo: Repository = Depends(get_repository),
) -> RedirectResponse:
    if action_choice not in _ACTION_MAP:
        raise HTTPException(status_code=400, detail=f"invalid action: {action_choice!r}")
    if not ticker.strip():
        raise HTTPException(status_code=400, detail="ticker required")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")
    if basis_or_proceeds < 0:
        raise HTTPException(status_code=400, detail="basis/proceeds must be >= 0")
    _validate_account(repo, account)
    d = _parse_date(trade_date)

    action, basis_source = _ACTION_MAP[action_choice]
    is_buy_side = action == "Buy"
    trade = Trade(
        id=trade_id,
        account=account,
        date=d,
        ticker=ticker.strip().upper(),
        action=action,
        quantity=quantity,
        cost_basis=basis_or_proceeds if is_buy_side else None,
        proceeds=basis_or_proceeds if not is_buy_side else None,
        basis_source=basis_source,
        is_manual=True,
    )
    etf_pairs = load_etf_pairs()
    try:
        saved = repo.update_manual_trade(trade, etf_pairs=etf_pairs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = RedirectResponse(url=f"/ticker/{saved.ticker}", status_code=303)
    response.headers["HX-Redirect"] = f"/ticker/{saved.ticker}"
    return response


@router.post("/trades/{trade_id}/edit-transfer", response_model=None)
def edit_transfer(
    request: Request,
    trade_id: str,
    seg_date: list[str] = Form(...),
    seg_qty: list[float] = Form(...),
    seg_basis: list[float] = Form(...),
    repo: Repository = Depends(get_repository),
) -> RedirectResponse:
    """Save segments for a transfer row.

    Single-segment payloads are equivalent to the legacy single-row edit;
    multi-segment payloads split the parent into N sibling rows that share
    a transfer_group_id.
    """
    if not (len(seg_date) == len(seg_qty) == len(seg_basis)) or not seg_date:
        raise HTTPException(status_code=400, detail="segment arrays must be non-empty and same length")

    segments: list[tuple[date, float, float]] = []
    for d_raw, q, b in zip(seg_date, seg_qty, seg_basis, strict=False):
        d = _parse_date(d_raw)
        if q <= 0:
            raise HTTPException(status_code=400, detail="segment qty must be > 0")
        if b < 0:
            raise HTTPException(status_code=400, detail="segment basis/proceeds must be >= 0")
        segments.append((d, float(q), float(b)))

    etf_pairs = load_etf_pairs()
    try:
        saved = repo.split_imported_transfer(
            trade_id=trade_id,
            segments=segments,
            etf_pairs=etf_pairs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    target = saved[0].ticker if saved else "?"
    response = RedirectResponse(url=f"/ticker/{target}", status_code=303)
    response.headers["HX-Redirect"] = f"/ticker/{target}"
    return response


@router.post("/trades/{trade_id}/delete", response_model=None)
def delete_trade(
    request: Request,
    trade_id: str,
    repo: Repository = Depends(get_repository),
) -> RedirectResponse:
    etf_pairs = load_etf_pairs()
    # Look up the ticker before deleting so we can redirect back.
    target_ticker = "?"
    for t in repo.all_trades():
        if t.id == trade_id:
            target_ticker = t.ticker
            break
    try:
        repo.delete_manual_trade(trade_id, etf_pairs=etf_pairs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = RedirectResponse(url=f"/ticker/{target_ticker}", status_code=303)
    response.headers["HX-Redirect"] = f"/ticker/{target_ticker}"
    return response

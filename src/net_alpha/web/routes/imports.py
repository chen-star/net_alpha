from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from net_alpha.brokers.registry import detect_broker
from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.ingest.csv_loader import compute_csv_sha256, load_csv
from net_alpha.ingest.dedup import filter_new
from net_alpha.models.domain import ImportRecord
from net_alpha.web.dependencies import get_etf_pairs, get_repository

router = APIRouter()


@router.get("/imports", response_class=HTMLResponse)
def imports_page(request: Request, repo: Repository = Depends(get_repository)) -> HTMLResponse:
    records = repo.list_imports()
    return request.app.state.templates.TemplateResponse(
        request,
        "imports.html",
        {"imports": records},
    )


@router.delete("/imports/{import_id}", response_class=HTMLResponse)
def remove_import(
    import_id: int,
    request: Request,
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    if repo.get_import(import_id) is None:
        raise HTTPException(status_code=404, detail=f"Import #{import_id} not found")

    result = repo.remove_import(import_id)
    if result.recompute_window is not None:
        win_start, win_end = result.recompute_window
        det = detect_in_window(
            repo.trades_in_window(win_start, win_end),
            win_start, win_end, etf_pairs=etf_pairs,
        )
        repo.replace_violations_in_window(win_start, win_end, det.violations)
        repo.replace_lots_in_window(win_start, win_end, det.lots)

    return request.app.state.templates.TemplateResponse(
        request,
        "_imports_table.html",
        {"imports": repo.list_imports()},
    )


def _save_to_temp(raw: bytes, filename: str) -> Path:
    suffix = Path(filename or "uploaded.csv").suffix or ".csv"
    fd = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    fd.write(raw)
    fd.close()
    return Path(fd.name)


@router.post("/imports/preview", response_class=HTMLResponse)
async def preview_upload(
    request: Request,
    file: UploadFile = File(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    raw = await file.read()
    tmp_path = _save_to_temp(raw, file.filename or "uploaded.csv")
    try:
        headers, rows = load_csv(str(tmp_path))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    parser = detect_broker(headers)
    accounts = [a.display() for a in repo.list_accounts()]
    preview_trades: list = []
    error: str | None = None
    if parser is None:
        error = "We couldn't detect a known broker format. Currently supported: Schwab."
    else:
        try:
            preview_trades = parser.parse(rows, account_display="schwab/preview")[:5]
        except Exception as exc:
            error = f"Parse error: {exc}"
    return request.app.state.templates.TemplateResponse(
        request,
        "_import_modal.html",
        {
            "broker_name": parser.name if parser else None,
            "filename": file.filename or "uploaded.csv",
            "accounts": accounts,
            "preview_trades": preview_trades,
            "error": error,
            "raw_size": len(raw),
        },
    )


@router.post("/imports", response_class=HTMLResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    account: str = Form(...),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    raw = await file.read()
    tmp_path = _save_to_temp(raw, file.filename or "uploaded.csv")
    try:
        headers, rows = load_csv(str(tmp_path))
        sha = compute_csv_sha256(str(tmp_path))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    parser = detect_broker(headers)
    if parser is None:
        raise HTTPException(status_code=400, detail="Unknown broker format")

    acct = repo.get_or_create_account(parser.name, account)
    trades = parser.parse(rows, account_display=acct.display())

    existing = repo.existing_natural_keys(acct.id)
    new_trades = filter_new(trades, existing)

    record = ImportRecord(
        account_id=acct.id,
        csv_filename=file.filename or "uploaded.csv",
        csv_sha256=sha,
        imported_at=datetime.now(),
        trade_count=len(new_trades),
    )
    result = repo.add_import(acct, record, new_trades)

    if new_trades:
        from datetime import timedelta

        win_start = min(t.date for t in new_trades) - timedelta(days=30)
        win_end = max(t.date for t in new_trades) + timedelta(days=30)
        det = detect_in_window(
            repo.trades_in_window(win_start, win_end),
            win_start,
            win_end,
            etf_pairs=etf_pairs,
        )
        repo.replace_violations_in_window(win_start, win_end, det.violations)
        repo.replace_lots_in_window(win_start, win_end, det.lots)

    dup_count = len(trades) - len(new_trades)
    return request.app.state.templates.TemplateResponse(
        request,
        "_toast.html",
        {
            "message": f"Imported {result.new_trades} new trades · skipped {dup_count} duplicates",
            "redirect_to": "/",
        },
    )

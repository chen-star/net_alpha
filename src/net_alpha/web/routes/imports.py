from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from net_alpha.brokers.registry import detect_broker
from net_alpha.brokers.schwab import SchwabParser
from net_alpha.brokers.schwab_realized_gl import SchwabRealizedGLParser
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.import_.aggregations import compute_import_aggregates
from net_alpha.ingest.csv_loader import load_csv
from net_alpha.ingest.dedup import filter_new
from net_alpha.models.domain import ImportRecord
from net_alpha.web.dependencies import get_etf_pairs, get_repository

router = APIRouter()


@router.get("/imports", response_class=HTMLResponse)
def imports_page(
    request: Request,
    flash: str | None = None,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    records = repo.list_imports()
    return request.app.state.templates.TemplateResponse(
        request,
        "imports.html",
        {"imports": records, "flash": flash},
    )


@router.delete("/imports/{import_id}", response_class=HTMLResponse)
def remove_import(
    import_id: int,
    request: Request,
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    existing_record = repo.get_import(import_id)
    if existing_record is None:
        raise HTTPException(status_code=404, detail=f"Import #{import_id} not found")
    account_id = existing_record.account_id
    result = repo.remove_import(import_id)
    if result.recompute_window is not None:
        # Re-stitch first so sells previously hydrated from now-deleted G/L lots
        # are demoted to FIFO/unknown before detection runs.
        stitch_account(repo, account_id)
        recompute_all_violations(repo, etf_pairs)
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


def _sha256_bytes(raw: bytes) -> str:
    h = hashlib.sha256()
    h.update(raw)
    return h.hexdigest()


@router.post("/imports/preview", response_class=HTMLResponse)
async def preview_upload(
    request: Request,
    files: list[UploadFile] = File(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    detections = []
    for f in files:
        raw = await f.read()
        tmp = _save_to_temp(raw, f.filename or "uploaded.csv")
        try:
            headers, rows = load_csv(str(tmp))
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        parser = detect_broker(headers)
        detections.append(
            {
                "filename": f.filename or "uploaded.csv",
                "size": len(raw),
                "parser_name": parser.name if parser else None,
                "row_count": len(rows),
            }
        )
    accounts = [a.display() for a in repo.list_accounts()]
    return request.app.state.templates.TemplateResponse(
        request,
        "_import_modal.html",
        {
            "detections": detections,
            "accounts": accounts,
            "any_recognized": any(d["parser_name"] for d in detections),
        },
    )


@router.post("/imports", response_class=HTMLResponse)
async def upload(
    request: Request,
    files: list[UploadFile] = File(...),
    account: str = Form(...),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    materialized = []
    for f in files:
        raw = await f.read()
        tmp = _save_to_temp(raw, f.filename or "uploaded.csv")
        try:
            headers, rows = load_csv(str(tmp))
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        parser = detect_broker(headers)
        materialized.append((f.filename or "uploaded.csv", raw, headers, rows, parser))

    if not any(p for *_, p in materialized):
        raise HTTPException(status_code=400, detail="No recognized broker formats among uploaded files")

    acct = repo.get_or_create_account("schwab", account)

    new_trade_count = 0
    dup_trade_count = 0
    new_gl_count = 0
    affected_dates: list = []

    for filename, raw, _headers, rows, parser in materialized:
        if parser is None:
            continue
        sha = _sha256_bytes(raw)
        if isinstance(parser, SchwabParser):
            trades = parser.parse(rows, account_display=acct.display())
            existing = repo.existing_natural_keys(acct.id)
            new_trades = filter_new(trades, existing)
            agg = compute_import_aggregates(trades=new_trades, parse_warnings=[])
            record = ImportRecord(
                account_id=acct.id,
                csv_filename=filename,
                csv_sha256=sha,
                imported_at=datetime.now(),
                trade_count=len(new_trades),
                min_trade_date=agg.min_trade_date,
                max_trade_date=agg.max_trade_date,
                equity_count=agg.equity_count,
                option_count=agg.option_count,
                option_expiry_count=agg.option_expiry_count,
                parse_warnings=agg.parse_warnings,
            )
            result = repo.add_import(acct, record, new_trades)
            new_trade_count += result.new_trades
            dup_trade_count += len(trades) - len(new_trades)
            for t in new_trades:
                affected_dates.append(t.date)
        elif isinstance(parser, SchwabRealizedGLParser):
            lots = parser.parse(rows, account_display=acct.display())
            gl_dates = [lot.closed_date for lot in lots] if lots else []
            min_d = min(gl_dates) if gl_dates else None
            max_d = max(gl_dates) if gl_dates else None
            equity_n = sum(1 for lot in lots if lot.option_strike is None)
            option_n = sum(1 for lot in lots if lot.option_strike is not None)
            record = ImportRecord(
                account_id=acct.id,
                csv_filename=filename,
                csv_sha256=sha,
                imported_at=datetime.now(),
                trade_count=0,
                min_trade_date=min_d,
                max_trade_date=max_d,
                equity_count=equity_n,
                option_count=option_n,
                option_expiry_count=0,
                parse_warnings=[],
            )
            empty_result = repo.add_import(acct, record, [])
            inserted = repo.add_gl_lots(acct, empty_result.import_id, lots)
            new_gl_count += inserted
            for lot in lots:
                affected_dates.append(lot.closed_date)

    stitched = stitch_account(repo, acct.id)

    if affected_dates:
        recompute_all_violations(repo, etf_pairs)

    msg_parts: list[str] = []
    if new_trade_count:
        msg_parts.append(f"Imported {new_trade_count} new trades")
    if dup_trade_count:
        msg_parts.append(f"skipped {dup_trade_count} duplicate trades")
    if new_gl_count:
        msg_parts.append(f"imported {new_gl_count} G/L lot rows")
    if stitched.from_gl:
        msg_parts.append(f"hydrated {stitched.from_gl} sells from G/L")
    if stitched.from_fifo:
        msg_parts.append(f"hydrated {stitched.from_fifo} sells via FIFO")
    if stitched.warnings:
        msg_parts.append(f"{len(stitched.warnings)} warning(s)")
    if not msg_parts:
        msg_parts.append("No changes")
    msg = " · ".join(msg_parts)
    return RedirectResponse(url=f"/imports?flash={quote(msg)}", status_code=303)

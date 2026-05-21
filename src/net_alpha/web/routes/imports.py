from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

import net_alpha.backup as backup
from net_alpha.audit.hygiene import collect_issues, collect_missing_basis_rows
from net_alpha.brokers.registry import detect_broker
from net_alpha.brokers.schwab_realized_gl import SchwabRealizedGLParser
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.import_.aggregations import compute_import_aggregates
from net_alpha.import_.positions_csv import (
    PositionsCSVParseError,
    parse_positions_csv,
)
from net_alpha.ingest.csv_loader import load_csv
from net_alpha.ingest.dedup import (
    filter_assignment_duplicates,
    filter_new,
    filter_sell_basis_drift_duplicates,
)
from net_alpha.models.domain import Account, ImportRecord
from net_alpha.prefs.profile import resolve_effective_profile
from net_alpha.service.jobs.runner import run_job
from net_alpha.service.jobs.washsale_watch import run_washsale_watch
from net_alpha.splits.sync import _post_import_autosync_splits
from net_alpha.web.account_filter import parse_accounts
from net_alpha.web.dependencies import get_etf_pairs, get_repository
from net_alpha.web.fragment_cache import bump_fragment_revision

router = APIRouter()

# Matches the "max 50 MB each" copy in the drop zone. Enforced server-side so
# a crafted POST can't silently buffer a gigabyte into the spool file.
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _check_upload_size(f: UploadFile, raw: bytes | None = None) -> None:
    """Reject uploads over the 50 MB cap. Inspects ``f.size`` when Starlette
    exposes it, then ``len(raw)`` after the read as a defence-in-depth check."""
    size = getattr(f, "size", None)
    if size is None and raw is not None:
        size = len(raw)
    if size is not None and size > _MAX_UPLOAD_BYTES:
        mb = size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"{(f.filename or 'file')!r} is {mb:.1f} MB; the limit is 50 MB.",
        )


def _enqueue_washsale_watch(request) -> None:
    """Add a one-shot washsale_watch job to the running scheduler.

    No-op when running in ephemeral mode (no scheduler on app.state).
    """
    sched = getattr(request.app.state, "scheduler", None)
    if sched is None:
        return
    state = getattr(request.app.state, "service_state", None)
    repo = getattr(request.app.state, "repository", None)
    if state is None or repo is None:
        return
    sched.add_job(
        func=run_job,
        kwargs={
            "job_name": "washsale_watch",
            "fn": lambda: run_washsale_watch(repo=repo),
            "state": state,
            "repo": repo,
        },
        id=f"washsale_watch_oneshot_{datetime.now(UTC).timestamp()}",
        run_date=datetime.now(UTC),
        misfire_grace_time=60,
    )


_IMPORTS_PAGE_SIZE = 25


def _paginate_imports(records: list, page: int, page_size: int) -> dict:
    total = len(records)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "imports": records[start:end],
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_count": total,
    }


@router.get("/imports/_legacy_page", response_class=HTMLResponse, include_in_schema=False)
def imports_page(
    request: Request,
    page: int = Query(1, ge=1),
    account: list[str] = Query(default_factory=list),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    """Render the legacy imports page body.

    Reachable only at the hidden ``/imports/_legacy_page`` URL — the
    Settings drawer's Imports tab fetches this fragment via HTMX
    (``hx-get="/imports/_legacy_page" hx-select="main > *"``) and
    surfaces it inline. Public ``/imports`` 301-redirects to
    ``/settings/imports`` (Phase 1 IA migration).
    """
    accounts: list[str] = parse_accounts(account)
    account_filter_active: bool = bool(accounts)

    records = repo.list_imports()
    accounts_available = sorted({imp.account_display for imp in records})

    # Filter import records by selected accounts (OR semantic).
    if accounts:
        accounts_set = set(accounts)
        records = [r for r in records if r.account_display in accounts_set]

    pagination = _paginate_imports(records, page=page, page_size=_IMPORTS_PAGE_SIZE)

    issues = collect_issues(repo)
    missing_basis_rows = collect_missing_basis_rows(repo)
    # HygieneIssue does not carry a per-account field (issues are DB-wide), so
    # the data-hygiene rollups remain unfiltered intentionally.
    # TODO: thread account filter into hygiene checks once HygieneIssue grows
    # an account field.

    prefs = repo.list_user_preferences()

    # Resolve single-account ID for provenance MetricRef encoding.
    filter_account_id: int | None = None
    if len(accounts) == 1:
        target = accounts[0]
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == target:
                filter_account_id = a.id
                break

    profile = resolve_effective_profile(prefs=prefs, filter_account_id=filter_account_id)

    DQ_LABELS = {
        "missing_basis": "Missing basis",
        "no_quote": "No price quote",
        "missing_dates": "Missing dates",
    }

    def _bucket_for(issue) -> str:
        cat = getattr(issue, "category", None) or ""
        if cat == "basis_unknown":
            return "missing_basis"
        if cat == "unpriced":
            return "no_quote"
        # Fall back to text-matching on summary/detail for unknown categories
        text = ((getattr(issue, "summary", None) or "") + " " + (getattr(issue, "detail", None) or "")).lower()
        if "basis" in text:
            return "missing_basis"
        if "quote" in text or "no price" in text or "unpriced" in text:
            return "no_quote"
        if "date" in text or "orphan" in text or "no matching" in text:
            return "missing_dates"
        return "missing_dates"  # default fallback bucket

    other_issues = [i for i in issues if getattr(i, "category", None) != "basis_unknown"]
    dq_groups: dict[str, list] = {"missing_basis": [], "no_quote": [], "missing_dates": []}
    for w in other_issues:
        dq_groups[_bucket_for(w)].append(w)

    return request.app.state.templates.TemplateResponse(
        request,
        "imports.html",
        {
            "imports": pagination["imports"],
            "page": pagination["page"],
            "page_size": pagination["page_size"],
            "total_pages": pagination["total_pages"],
            "total_count": pagination["total_count"],
            "issues": issues,
            "missing_basis_rows": missing_basis_rows,
            "dq_groups": dq_groups,
            "dq_labels": DQ_LABELS,
            "profile": profile,
            "page_key": "/imports",
            "account_id": filter_account_id,
            "selected_account": accounts[0] if len(accounts) == 1 else "",
            "selected_accounts": accounts,
            "accounts_available": accounts_available,
            "account_filter_active": account_filter_active,
        },
    )


@router.delete("/imports/{import_id}", response_class=HTMLResponse)
def remove_import(
    import_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    existing_record = repo.get_import(import_id)
    if existing_record is None:
        raise HTTPException(status_code=404, detail=f"Import #{import_id} not found")
    # Mirror the CLI (cli/imports.py:25): a pre-mutation snapshot makes the
    # delete recoverable. Without this the UI path silently loses data the
    # CLI path preserves.
    backup.snapshot_pre(reason="pre-imports-rm")
    account_id = existing_record.account_id
    result = repo.remove_import(import_id)
    if result.recompute_window is not None:
        # Re-stitch first so sells previously hydrated from now-deleted G/L lots
        # are demoted to FIFO/unknown before detection runs.
        stitch_account(repo, account_id)
        recompute_all_violations(repo, etf_pairs)
    bump_fragment_revision(request)
    pagination = _paginate_imports(repo.list_imports(), page=page, page_size=_IMPORTS_PAGE_SIZE)
    return request.app.state.templates.TemplateResponse(
        request,
        "_imports_table.html",
        {
            "imports": pagination["imports"],
            "page": pagination["page"],
            "page_size": pagination["page_size"],
            "total_pages": pagination["total_pages"],
            "total_count": pagination["total_count"],
        },
    )


@router.post("/imports/bulk-delete", response_class=HTMLResponse)
def bulk_remove_imports(
    request: Request,
    ids: list[int] = Form([]),
    page: int = Query(1, ge=1),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    # Pre-mutation snapshot (mirrors the per-id DELETE path). Take it once
    # outside the loop so a bulk delete of N imports produces a single
    # backup, not N.
    if ids:
        backup.snapshot_pre(reason="pre-imports-rm")
    affected_account_ids: set[int] = set()
    needs_recompute = False
    for import_id in ids:
        existing = repo.get_import(import_id)
        if existing is None:
            continue
        result = repo.remove_import(import_id)
        if result.recompute_window is not None:
            affected_account_ids.add(existing.account_id)
            needs_recompute = True
    # Re-stitch each affected account once, then a single global recompute —
    # cheaper than per-import work when the user clears many at once.
    for acct_id in affected_account_ids:
        stitch_account(repo, acct_id)
    if needs_recompute:
        recompute_all_violations(repo, etf_pairs)
    if ids:
        bump_fragment_revision(request)
    pagination = _paginate_imports(repo.list_imports(), page=page, page_size=_IMPORTS_PAGE_SIZE)
    return request.app.state.templates.TemplateResponse(
        request,
        "_imports_table.html",
        {
            "imports": pagination["imports"],
            "page": pagination["page"],
            "page_size": pagination["page_size"],
            "total_pages": pagination["total_pages"],
            "total_count": pagination["total_count"],
        },
    )


@router.get("/imports/{import_id}/detail", response_class=HTMLResponse)
def import_detail(
    import_id: int,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    detail = repo.get_import_detail(import_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Import #{import_id} not found")
    return request.app.state.templates.TemplateResponse(
        request,
        "_imports_detail_row.html",
        {"detail": detail},
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
    sample_trades: list = []
    total_parsed = 0
    for f in files:
        _check_upload_size(f)
        raw = await f.read()
        _check_upload_size(f, raw=raw)
        tmp = _save_to_temp(raw, f.filename or "uploaded.csv")
        try:
            headers, rows = load_csv(str(tmp))
        except UnicodeDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{(f.filename or 'file')!r} isn't a UTF-8 text file "
                    f"(decode failed at byte {e.start}). Save as plain CSV and retry."
                ),
            ) from e
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
        if hasattr(parser, "parse_full"):
            parsed = parser.parse_full(rows, account_display="preview/preview")
            total_parsed += len(parsed.trades)
            for t in parsed.trades:
                if len(sample_trades) >= 5:
                    break
                sample_trades.append(t)
    accounts = [a.display() for a in repo.list_accounts()]
    return request.app.state.templates.TemplateResponse(
        request,
        "_import_modal.html",
        {
            "detections": detections,
            "accounts": accounts,
            "any_recognized": any(d["parser_name"] for d in detections),
            "sample_trades": sample_trades,
            "total_parsed": total_parsed,
        },
    )


@router.post("/imports", response_class=HTMLResponse)
async def upload(
    request: Request,
    files: list[UploadFile] = File(...),
    account: list[str] = Form(...),
    repo: Repository = Depends(get_repository),
    etf_pairs: dict = Depends(get_etf_pairs),
) -> HTMLResponse:
    if request.app.state.demo_mode:
        return RedirectResponse("/welcome", status_code=303)

    # Mirror the CLI (cli/default.py:73): a pre-import snapshot lets the user
    # roll back an unintended ingest. Take it before any DB write — file
    # parsing failures below this point won't have mutated the DB anyway,
    # so a wasted snapshot is harmless and the failure-tolerant path is right.
    backup.snapshot_pre(reason="pre-import")

    # Per-file account labels. The modal renders one input per file when
    # multiple are uploaded so the user can route each file to its own
    # account; without this, dropping two CSVs from different accounts
    # silently collapses them into one and breaks cross-account wash-sale
    # detection (+ the Rev. Rul. 2008-5 IRA-trap classifier).
    if len(account) == 1:
        per_file_labels = [account[0]] * len(files)
    elif len(account) == len(files):
        per_file_labels = list(account)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"account count ({len(account)}) must equal file count ({len(files)}) "
                "or be a single label applied to every file"
            ),
        )
    if any(not (lbl and lbl.strip()) for lbl in per_file_labels):
        raise HTTPException(status_code=400, detail="every file requires a non-empty account label")

    materialized = []
    for f, file_label in zip(files, per_file_labels, strict=True):
        _check_upload_size(f)
        raw = await f.read()
        _check_upload_size(f, raw=raw)
        tmp = _save_to_temp(raw, f.filename or "uploaded.csv")
        try:
            headers, rows = load_csv(str(tmp))
        except UnicodeDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{(f.filename or 'file')!r} isn't a UTF-8 text file "
                    f"(decode failed at byte {e.start}). Save as plain CSV and retry."
                ),
            ) from e
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        parser = detect_broker(headers)
        materialized.append((f.filename or "uploaded.csv", raw, headers, rows, parser, file_label))

    if not any(m[4] for m in materialized):
        raise HTTPException(status_code=400, detail="No recognized broker formats among uploaded files")

    accounts: dict[tuple[str, str], Account] = {}

    existing_symbols = {lot.ticker for lot in repo.all_lots() if lot.option_details is None}
    new_trade_count = 0
    dup_trade_count = 0
    new_gl_count = 0
    affected_dates: list = []
    new_symbols: set[str] = set()
    last_import_id: int | None = None

    for filename, raw, _headers, rows, parser, file_label in materialized:
        if parser is None:
            continue
        # SchwabRealizedGLParser stores GL lots under the same "schwab" broker account
        # as SchwabParser — use parser.name unless it's the GL variant.
        broker_key = "schwab" if isinstance(parser, SchwabRealizedGLParser) else parser.name
        key = (broker_key, file_label)
        if key not in accounts:
            accounts[key] = repo.get_or_create_account(broker_key, file_label)
        acct = accounts[key]
        sha = _sha256_bytes(raw)
        if hasattr(parser, "parse_full"):
            import_result = parser.parse_full(rows, account_display=acct.display())
            trades = import_result.trades
            existing = repo.existing_natural_keys(acct.id)
            new_trades = filter_new(trades, existing)
            # Second-pass dedup #1: drop re-imported equity Sells whose only
            # difference from an existing Sell is ``cost_basis`` (Schwab can
            # add a populated "Cost Basis" column between exports, flipping
            # the natural_key on otherwise-identical sells).
            pre_basis_drift = len(new_trades)
            new_trades = filter_sell_basis_drift_duplicates(
                new_trades, existing_keys=repo.existing_sell_basis_blind_keys(acct.id)
            )
            # Second-pass dedup #2: drop plain underlying-Buy rows that duplicate
            # an existing put_assignment trade. Schwab's CSV records each put
            # assignment as Assigned + Buy; partial re-imports that lack the
            # Assigned row would otherwise create unadjusted-basis duplicates.
            existing_assignments = repo.existing_put_assignment_keys(acct.id)
            pre_assignment_dedup = len(new_trades)
            new_trades = filter_assignment_duplicates(new_trades, existing_assignments=existing_assignments)
            pre_filtered_dups = (
                (len(trades) - pre_basis_drift)
                + (pre_basis_drift - pre_assignment_dedup)
                + (pre_assignment_dedup - len(new_trades))
            )
            # Aggregates are derived from the *parsed* set so a re-import that
            # filters everything still records the file's date range and counts
            # — the imports page can then show "skipped 7 dupes · 04/14 → 11/14"
            # rather than empty fields.
            agg = compute_import_aggregates(trades=trades, parse_warnings=import_result.parse_warnings)
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
                duplicate_trades=pre_filtered_dups,
            )
            result = repo.add_import(acct, record, new_trades, cash_events=import_result.cash_events)
            new_trade_count += result.new_trades
            dup_trade_count += pre_filtered_dups
            last_import_id = result.import_id
            for t in new_trades:
                affected_dates.append(t.date)
                if t.option_details is None:
                    new_symbols.add(t.ticker)
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
            last_import_id = empty_result.import_id
            for lot in lots:
                affected_dates.append(lot.closed_date)

    for a in accounts.values():
        stitch_account(repo, a.id)

    if affected_dates:
        recompute_all_violations(repo, etf_pairs)

    _post_import_autosync_splits(repo, new_symbols=new_symbols, existing_symbols=existing_symbols)

    _enqueue_washsale_watch(request)

    if new_trade_count or new_gl_count:
        bump_fragment_revision(request)

    if last_import_id is not None:
        return RedirectResponse(url=f"/imports/success?id={last_import_id}", status_code=303)
    return RedirectResponse(url="/settings/imports", status_code=303)


@router.post("/imports/positions", response_model=None)
async def upload_positions_csv(
    request: Request,
    file: UploadFile = File(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse | RedirectResponse:
    """Ingest a Schwab All-Positions CSV → ``broker_position`` rows.

    The parsed rows + the as-of date from the CSV header are persisted via
    :meth:`Repository.save_broker_positions`, which also writes a sentinel
    ImportRecord so the row surfaces on the Imports page. A verify run is
    then triggered best-effort (failures don't block — the verify-job
    orchestrator is wired in a later phase).
    """
    if request.app.state.demo_mode:
        return RedirectResponse("/welcome", status_code=303)

    _check_upload_size(file)
    raw = await file.read()
    _check_upload_size(file, raw=raw)
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{(file.filename or 'file')!r} isn't a UTF-8 text file "
                f"(decode failed at byte {e.start}). Export as plain CSV and retry."
            ),
        ) from e
    try:
        rows, as_of = parse_positions_csv(content)
    except PositionsCSVParseError as e:
        raise HTTPException(status_code=400, detail=f"Could not parse positions CSV: {e}") from e

    import_id = repo.save_broker_positions(rows=rows, as_of_date=as_of)

    bump_fragment_revision(request)

    # If any row's account_label didn't resolve to an existing account
    # (neither accounts.label nor accounts.broker_label match), redirect
    # to the alias picker BEFORE running verify — running verify against
    # unmapped labels would just produce noise (109 missing-local/missing-
    # broker findings for what is actually the same data).
    if repo.unresolved_broker_labels(import_id=import_id):
        return RedirectResponse(
            url=f"/imports/positions/map?import_id={import_id}",
            status_code=303,
        )

    # All labels resolved — safe to verify now.
    try:  # pragma: no cover - exercised once Phase 5 lands
        from net_alpha.service.jobs.verify import run_verify_once

        run_verify_once(repo=repo, trigger="positions_import")
    except Exception:  # noqa: BLE001
        pass

    return RedirectResponse(url=f"/settings/imports?highlight={import_id}", status_code=303)


@router.get("/imports/positions/map", response_class=HTMLResponse, response_model=None)
def positions_map_picker(
    request: Request,
    import_id: int = Query(...),
    repo: Repository = Depends(get_repository),
) -> HTMLResponse | RedirectResponse:
    """Render the picker that maps each unresolved broker label to an
    existing user account. Bypassed automatically when nothing is left
    to map (e.g. the user reloads the page after submitting)."""
    unresolved = repo.unresolved_broker_labels(import_id=import_id)
    if not unresolved:
        return RedirectResponse(url="/verify", status_code=303)
    # Real user accounts only — the "(multi)" sentinel created by
    # save_broker_positions is not selectable as a mapping target.
    accounts = [a for a in repo.list_accounts() if not (a.broker == "positions" and a.label == "(multi)")]
    return request.app.state.templates.TemplateResponse(
        request,
        "imports_positions_map.html",
        {
            "import_id": import_id,
            "unresolved": unresolved,
            "accounts": accounts,
        },
    )


@router.post("/imports/positions/map", response_model=None)
def positions_map_apply(
    request: Request,
    import_id: int = Form(...),
    broker_label: list[str] = Form(...),
    account_id: list[str] = Form(...),
    repo: Repository = Depends(get_repository),
) -> RedirectResponse:
    """Apply the picker's mapping: register each broker_label as an alias
    on the chosen account, retag broker_position rows, run verify, and
    send the user to the verify dashboard to see the now-correct findings.

    ``account_id`` may be the literal string "skip" for labels the user
    chooses to leave unmapped — those rows stay with their raw broker
    label and continue to surface in future picker invocations.
    """
    if len(broker_label) != len(account_id):
        raise HTTPException(status_code=400, detail="mapping form is malformed")
    for raw, aid in zip(broker_label, account_id, strict=True):
        if aid == "skip" or not aid:
            continue
        try:
            repo.set_account_broker_alias(account_id=int(aid), broker_label=raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    bump_fragment_revision(request)

    try:  # pragma: no cover - service job not wired in unit tests
        from net_alpha.service.jobs.verify import run_verify_once

        run_verify_once(repo=repo, trigger="positions_import")
    except Exception:  # noqa: BLE001
        pass

    return RedirectResponse(url="/verify", status_code=303)


@router.get("/imports/success", response_class=HTMLResponse)
def imports_success(
    request: Request,
    id: int,
    repo: Repository = Depends(get_repository),
) -> HTMLResponse:
    record = repo.get_import(id)
    if record is None:
        return RedirectResponse(url="/settings/imports", status_code=303)

    trades_in_import = repo.trades_for_import(id)
    trade_ids_in_import = {t.id for t in trades_in_import}
    violations_in_import = [v for v in repo.all_violations() if v.loss_trade_id in trade_ids_in_import]
    disallowed_total = sum(v.disallowed_loss for v in violations_in_import)

    return request.app.state.templates.TemplateResponse(
        request,
        "imports_success.html",
        {
            "trade_count": len(trades_in_import),
            "wash_sale_count": len(violations_in_import),
            "disallowed_total": disallowed_total,
            "import_id": id,
        },
    )

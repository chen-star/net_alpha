from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
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

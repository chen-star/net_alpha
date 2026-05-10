from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from net_alpha import __version__ as _app_version
from net_alpha.audit import encode_metric_ref as _encode_metric_ref
from net_alpha.config import Settings, load_pricing_config, load_tax_config
from net_alpha.db.connection import get_engine, init_db
from net_alpha.engine.etf_pairs import load_etf_pairs, load_etf_replacements
from net_alpha.output.disclaimer import price_source_line
from net_alpha.output.disclaimer import render as disclaimer_render
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.yahoo import YahooPriceProvider
from net_alpha.web.dependencies import effective_db_path
from net_alpha.web.format import fmt_currency, fmt_date, fmt_percent, fmt_quantity
from net_alpha.web.fragment_cache import FragmentCache
from net_alpha.web.routes import (
    audit_routes,
    positions,
    redirects,
    sim,
    system,
    ticker,
    tour,
    trades,
    wash_sales,
    welcome,
)
from net_alpha.web.routes import imports as imports_routes
from net_alpha.web.routes import portfolio as portfolio_routes
from net_alpha.web.routes import preferences as preferences_routes
from net_alpha.web.routes import service as service_routes
from net_alpha.web.routes import settings as settings_routes
from net_alpha.web.routes import tax as tax_routes
from net_alpha.web.routes.accounts import router as accounts_router


def create_app(settings: Settings | None = None, demo_mode: bool = False) -> FastAPI:
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Start the background scheduler on boot; shut it down cleanly on exit.

        Skipped when NETALPHA_SKIP_SCHEDULER=1 (test environments).
        """
        if os.environ.get("NETALPHA_SKIP_SCHEDULER") != "1":
            try:
                from net_alpha.db.connection import get_engine
                from net_alpha.db.repository import Repository
                from net_alpha.service import disabled_flag
                from net_alpha.service.scheduler import build_scheduler
                from net_alpha.service.state import ServiceState

                state = ServiceState()
                # Repository is not stored on app.state in this factory — each
                # request creates its own engine via effective_db_path.  We build
                # a dedicated repo for the scheduler using the canonical db_path.
                repo = getattr(app.state, "repository", None)
                if repo is None:
                    _sched_engine = get_engine(app.state.settings.db_path)
                    repo = Repository(_sched_engine)
                # pricing is not wired onto app.state in this factory; pass None
                # so the price_refresh job fails fast on the actual fetch call
                # rather than crashing at scheduler registration time.
                pricing = getattr(app.state, "pricing", None)
                sched = build_scheduler(repo=repo, pricing=pricing, state=state)
                if not disabled_flag.is_set():
                    sched.start()
                app.state.scheduler = sched
                app.state.service_state = state
            except Exception:
                # Never crash the web UI because the scheduler failed to start.
                import logging

                logging.getLogger(__name__).exception(
                    "Scheduler startup failed — web UI will continue without background jobs."
                )

        yield

        # Shutdown phase: stop the scheduler if it was started.
        sched = getattr(app.state, "scheduler", None)
        if sched is not None and getattr(sched, "running", False):
            sched.shutdown(wait=False)

    app = FastAPI(title="net-alpha", lifespan=_lifespan)
    app.state.settings = settings
    app.state.demo_mode = demo_mode
    app.state.etf_pairs = load_etf_pairs(user_path=str(settings.user_etf_pairs_path))
    app.state.etf_replacements = load_etf_replacements(
        user_path=settings.data_dir / "etf_replacements.yaml",
        etf_pairs=app.state.etf_pairs,
    )
    app.state.tax_brackets_cfg = load_tax_config(settings.config_yaml_path)

    # Ensure the database schema exists before accepting requests.
    engine = get_engine(settings.db_path)
    init_db(engine)

    pricing_config = load_pricing_config(settings.config_yaml_path)
    app.state.pricing_config = pricing_config
    app.state.price_provider = YahooPriceProvider() if pricing_config.source == "yahoo" else None
    app.state.price_cache = PriceCache(engine, ttl_seconds=pricing_config.cache_ttl_seconds)

    # Fragment-level cache for the dashboard's heavy compute. Keyed on
    # (route_path, params, fragment_revision); revision is bumped by write
    # endpoints (see fragment_cache.bump_fragment_revision).
    app.state.fragment_cache = FragmentCache(ttl_seconds=60)
    app.state.fragment_revision = 0

    static_dir = files("net_alpha.web") / "static"
    templates_dir = files("net_alpha.web") / "templates"

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    templates = Jinja2Templates(directory=str(templates_dir))
    templates.env.globals["disclaimer"] = disclaimer_render()
    templates.env.globals["price_disclosure"] = (
        price_source_line("Yahoo Finance") if pricing_config.enable_remote else ""
    )
    # Bust browser cache on every server start — local dev tool, not a CDN, so
    # the server-restart cadence is the right TTL for static assets.
    templates.env.globals["asset_v"] = str(int(time.time()))
    templates.env.globals["encode_metric_ref"] = _encode_metric_ref

    def _imports_badge_count() -> int:
        from net_alpha.audit._badge_cache import get_imports_badge_count
        from net_alpha.db.repository import Repository as _Repository

        _engine = get_engine(effective_db_path(settings, app.state.demo_mode))
        return get_imports_badge_count(_Repository(_engine), settings=settings)

    templates.env.globals["imports_badge_count"] = _imports_badge_count

    @pass_context
    def _profile_switcher_data(ctx) -> dict[str, object]:
        from net_alpha.db.repository import Repository as _Repository
        from net_alpha.prefs.profile import (
            DEFAULT_PROFILE_SETTINGS,
            resolve_effective_profile,
        )

        request = ctx.get("request")
        account = None
        if request is not None:
            account = request.query_params.get("account")

        _engine = get_engine(effective_db_path(settings, app.state.demo_mode))
        _repo = _Repository(_engine)
        accounts = _repo.list_accounts()
        prefs = _repo.list_user_preferences()
        filter_id: int | None = None
        if account:
            for a in accounts:
                if f"{a.broker}/{a.label}" == account:
                    filter_id = a.id
                    break
        prof_by_id = {p.account_id: p.profile for p in prefs}
        profile = resolve_effective_profile(prefs=prefs, filter_account_id=filter_id)
        return {
            "accounts": accounts,
            "account_profiles": prof_by_id,
            "profile": profile if accounts else DEFAULT_PROFILE_SETTINGS,
            "show_switcher": bool(accounts),
        }

    templates.env.globals["profile_switcher_data"] = _profile_switcher_data
    templates.env.globals["fmt_quantity"] = fmt_quantity
    templates.env.globals["fmt_currency"] = fmt_currency
    templates.env.globals["fmt_percent"] = fmt_percent
    templates.env.globals["fmt_date"] = fmt_date

    def _first_visit_modal_data() -> dict[str, object]:
        from net_alpha.db.repository import Repository as _Repository

        _engine = get_engine(effective_db_path(settings, app.state.demo_mode))
        _repo = _Repository(_engine)
        accounts = _repo.list_accounts()
        prefs = _repo.list_user_preferences()
        return {
            "show_modal": bool(accounts) and not prefs,
            "accounts": accounts,
        }

    templates.env.globals["first_visit_modal_data"] = _first_visit_modal_data

    def _palette_index_json() -> str:
        """Bootstrap blob for the ⌘K palette. Re-built on every render so new
        imports / targets appear immediately on the next navigation.

        Filtering happens client-side in static/palette.js; this returns
        only the data."""
        import json as _json

        from net_alpha.db.repository import Repository as _Repository
        from net_alpha.web.palette import build_palette_index

        _engine = get_engine(effective_db_path(settings, app.state.demo_mode))
        return _json.dumps(build_palette_index(_Repository(_engine)), separators=(",", ":"))

    templates.env.globals["palette_index_json"] = _palette_index_json

    templates.env.globals["app_version"] = _app_version
    templates.env.globals["data_dir_path"] = str(settings.data_dir)
    templates.env.globals["pricing_remote_enabled"] = pricing_config.enable_remote

    def _etf_pairs_data() -> dict[str, object]:
        return {
            "groups": app.state.etf_pairs,
            "user_file_path": str(settings.user_etf_pairs_path),
            "user_file_exists": settings.user_etf_pairs_path.exists(),
        }

    templates.env.globals["etf_pairs_data"] = _etf_pairs_data

    # Register Python built-ins as Jinja2 filters that templates use.
    templates.env.filters["ord"] = ord

    app.state.templates = templates

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(audit_routes.router)
    app.include_router(preferences_routes.router)
    app.include_router(redirects.router)
    app.include_router(welcome.router)
    app.include_router(tour.router)
    app.include_router(service_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(accounts_router)
    app.include_router(tax_routes.router)
    app.include_router(wash_sales.router)
    app.include_router(positions.router)
    app.include_router(imports_routes.router)
    app.include_router(sim.router)
    app.include_router(ticker.router)
    app.include_router(portfolio_routes.router)
    app.include_router(trades.router)
    app.include_router(system.router)

    system.register_error_handlers(app)

    return app

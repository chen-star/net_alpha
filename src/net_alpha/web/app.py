from __future__ import annotations

import time
from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from net_alpha.audit import encode_metric_ref as _encode_metric_ref
from net_alpha.config import Settings, load_pricing_config, load_tax_config
from net_alpha.db.connection import get_engine, init_db
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.output.disclaimer import price_source_line
from net_alpha.output.disclaimer import render as disclaimer_render
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.yahoo import YahooPriceProvider
from net_alpha.web.routes import audit_routes, holdings, sim, system, ticker, trades, wash_sales
from net_alpha.web.routes import imports as imports_routes
from net_alpha.web.routes import portfolio as portfolio_routes


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="net-alpha")
    app.state.settings = settings
    app.state.etf_pairs = load_etf_pairs(user_path=str(settings.user_etf_pairs_path))
    app.state.tax_brackets_cfg = load_tax_config(settings.config_yaml_path)

    # Ensure the database schema exists before accepting requests.
    engine = get_engine(settings.db_path)
    init_db(engine)

    pricing_config = load_pricing_config(settings.config_yaml_path)
    app.state.pricing_config = pricing_config
    app.state.price_provider = YahooPriceProvider() if pricing_config.source == "yahoo" else None
    app.state.price_cache = PriceCache(engine, ttl_seconds=pricing_config.cache_ttl_seconds)

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

        _engine = get_engine(settings.db_path)
        return get_imports_badge_count(_Repository(_engine), settings=settings)

    templates.env.globals["imports_badge_count"] = _imports_badge_count
    app.state.templates = templates

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(audit_routes.router)
    app.include_router(wash_sales.router)
    app.include_router(holdings.router)
    app.include_router(imports_routes.router)
    app.include_router(sim.router)
    app.include_router(ticker.router)
    app.include_router(portfolio_routes.router)
    app.include_router(trades.router)
    app.include_router(system.router)

    system.register_error_handlers(app)

    return app

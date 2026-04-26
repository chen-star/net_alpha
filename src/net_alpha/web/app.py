from __future__ import annotations

from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from net_alpha.config import Settings, load_pricing_config
from net_alpha.db.connection import get_engine, init_db
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.output.disclaimer import render as disclaimer_render
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.yahoo import YahooPriceProvider
from net_alpha.web.routes import calendar, dashboard, detail, sim, system, ticker
from net_alpha.web.routes import imports as imports_routes


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="net-alpha")
    app.state.settings = settings
    app.state.etf_pairs = load_etf_pairs(user_path=str(settings.user_etf_pairs_path))

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
    app.state.templates = templates

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(calendar.router)
    app.include_router(dashboard.router)
    app.include_router(imports_routes.router)
    app.include_router(detail.router)
    app.include_router(sim.router)
    app.include_router(ticker.router)
    app.include_router(system.router)

    system.register_error_handlers(app)

    return app

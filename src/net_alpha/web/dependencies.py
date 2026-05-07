from __future__ import annotations

from pathlib import Path

from fastapi import Request

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.prefs.profile import ProfileSettings, resolve_effective_profile
from net_alpha.pricing.service import PricingService


def effective_db_path(settings: Settings, demo_mode: bool) -> Path:
    """SQLite path for this request; demo_mode routes to <data_dir>/demo.db."""
    if demo_mode:
        return settings.data_dir / "demo.db"
    return settings.db_path


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_repository(request: Request) -> Repository:
    settings: Settings = request.app.state.settings
    demo_mode: bool = request.app.state.demo_mode
    engine = get_engine(effective_db_path(settings, demo_mode))
    return Repository(engine)


def get_etf_pairs(request: Request) -> dict[str, list[str]]:
    return request.app.state.etf_pairs


def get_pricing_service(request: Request) -> PricingService:
    return PricingService(
        provider=request.app.state.price_provider,
        cache=request.app.state.price_cache,
        enabled=request.app.state.pricing_config.enable_remote and request.app.state.price_provider is not None,
    )


def get_profile_settings(
    request: Request,
    account: str | None = None,
) -> ProfileSettings:
    """Resolve the rendering profile for the current request.

    Reads the optional `account` query string (display form 'Broker/Label'),
    looks up the account id, and merges per-account preferences according to
    `resolve_effective_profile`.
    """
    settings: Settings = request.app.state.settings
    demo_mode: bool = request.app.state.demo_mode
    engine = get_engine(effective_db_path(settings, demo_mode))
    repo = Repository(engine)
    prefs = repo.list_user_preferences()
    filter_id: int | None = None
    if account:
        for a in repo.list_accounts():
            if f"{a.broker}/{a.label}" == account:
                filter_id = a.id
                break
    return resolve_effective_profile(prefs=prefs, filter_account_id=filter_id)

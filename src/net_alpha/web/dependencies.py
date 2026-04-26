from __future__ import annotations

from fastapi import Request

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.pricing.service import PricingService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_repository(request: Request) -> Repository:
    settings: Settings = request.app.state.settings
    engine = get_engine(settings.db_path)
    return Repository(engine)


def get_etf_pairs(request: Request) -> dict[str, list[str]]:
    return request.app.state.etf_pairs


def get_pricing_service(request: Request) -> PricingService:
    return PricingService(
        provider=request.app.state.price_provider,
        cache=request.app.state.price_cache,
        enabled=request.app.state.pricing_config.enable_remote and request.app.state.price_provider is not None,
    )

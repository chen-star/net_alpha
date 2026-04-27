from __future__ import annotations

from net_alpha.pricing.provider import PriceFetchError


def _post_import_autosync_splits(
    repo,
    *,
    new_symbols: set[str],
    existing_symbols: set[str],
) -> None:
    """If pricing is enabled and there are symbols seen for the first time
    in this DB, fetch their splits so the user doesn't have to remember to
    click Sync splits."""
    from net_alpha.config import Settings, load_pricing_config
    from net_alpha.pricing.cache import PriceCache
    from net_alpha.pricing.service import PricingService
    from net_alpha.pricing.yahoo import YahooPriceProvider

    truly_new = new_symbols - existing_symbols
    if not truly_new:
        return

    cfg = load_pricing_config(Settings().config_yaml_path)
    if not cfg.enable_remote:
        return

    cache = PriceCache(repo.engine, ttl_seconds=cfg.cache_ttl_seconds)
    svc = PricingService(provider=YahooPriceProvider(), cache=cache, enabled=True)
    try:
        svc.sync_splits(sorted(truly_new), repo=repo)
    except (ConnectionError, TimeoutError, PriceFetchError):
        # Network/provider failures are best-effort: don't block import.
        pass

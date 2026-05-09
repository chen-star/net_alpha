from unittest.mock import MagicMock

from net_alpha.service.jobs.price_refresh import run_price_refresh


def test_run_price_refresh_collects_symbols_and_calls_pricing():
    repo = MagicMock()
    repo.distinct_held_tickers.return_value = ["SPY", "TSLA"]
    repo.distinct_target_tickers.return_value = ["TSLA", "QQQ"]
    pricing = MagicMock()

    payload = run_price_refresh(repo=repo, pricing=pricing)

    pricing.refresh.assert_called_once()
    args = pricing.refresh.call_args.args
    assert sorted(args[0]) == ["QQQ", "SPY", "TSLA"]
    assert payload == {"symbols": 3}


def test_run_price_refresh_returns_zero_with_nothing_held():
    repo = MagicMock()
    repo.distinct_held_tickers.return_value = []
    repo.distinct_target_tickers.return_value = []
    pricing = MagicMock()
    payload = run_price_refresh(repo=repo, pricing=pricing)
    assert payload == {"symbols": 0}
    pricing.refresh.assert_not_called()

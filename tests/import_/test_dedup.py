from datetime import date
from unittest.mock import MagicMock

from net_alpha.import_.dedup import deduplicate_trades
from net_alpha.models.domain import Trade


def _make_trade(**kwargs) -> Trade:
    defaults = {
        "account": "Schwab",
        "date": date(2024, 10, 15),
        "ticker": "TSLA",
        "action": "Buy",
        "quantity": 10.0,
        "proceeds": None,
        "cost_basis": 2400.0,
        "raw_row_hash": "hash_abc",
    }
    defaults.update(kwargs)
    return Trade(**defaults)


def test_no_duplicates_all_new():
    trades = [_make_trade(raw_row_hash="h1"), _make_trade(raw_row_hash="h2")]
    mock_repo = MagicMock()
    mock_repo.find_by_hash.return_value = None
    mock_repo.find_by_semantic_key.return_value = None

    new, skipped = deduplicate_trades(trades, mock_repo)
    assert len(new) == 2
    assert skipped == 0


def test_hash_duplicate_skipped():
    trades = [_make_trade(raw_row_hash="existing_hash")]
    mock_repo = MagicMock()
    mock_repo.find_by_hash.return_value = _make_trade()  # Exists

    new, skipped = deduplicate_trades(trades, mock_repo)
    assert len(new) == 0
    assert skipped == 1


def test_semantic_key_duplicate_skipped():
    trades = [_make_trade(raw_row_hash="new_hash")]
    mock_repo = MagicMock()
    mock_repo.find_by_hash.return_value = None
    mock_repo.find_by_semantic_key.return_value = _make_trade()  # Semantic match

    new, skipped = deduplicate_trades(trades, mock_repo)
    assert len(new) == 0
    assert skipped == 1


def test_mixed_new_and_duplicate():
    trades = [
        _make_trade(raw_row_hash="new1", ticker="TSLA"),
        _make_trade(raw_row_hash="existing", ticker="AAPL"),
        _make_trade(raw_row_hash="new2", ticker="NVDA"),
    ]
    mock_repo = MagicMock()

    def hash_lookup(h):
        return _make_trade() if h == "existing" else None

    mock_repo.find_by_hash.side_effect = hash_lookup
    mock_repo.find_by_semantic_key.return_value = None

    new, skipped = deduplicate_trades(trades, mock_repo)
    assert len(new) == 2
    assert skipped == 1


def test_null_hash_uses_semantic_key_only():
    trades = [_make_trade(raw_row_hash=None)]
    mock_repo = MagicMock()
    mock_repo.find_by_hash.return_value = None
    mock_repo.find_by_semantic_key.return_value = None

    new, skipped = deduplicate_trades(trades, mock_repo)
    assert len(new) == 1
    # Should not call find_by_hash with None
    mock_repo.find_by_hash.assert_not_called()

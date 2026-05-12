from net_alpha.web.account_filter import parse_accounts


def test_empty_input_returns_empty_list():
    assert parse_accounts([]) == []


def test_strips_empty_strings():
    # "?account=" maps to [""] in FastAPI; treat as "All accounts"
    assert parse_accounts(["", ""]) == []


def test_strips_whitespace_only():
    assert parse_accounts(["  ", "Schwab/Personal"]) == ["Schwab/Personal"]


def test_dedupes_preserving_first_seen_order():
    assert parse_accounts(["B", "A", "B", "A"]) == ["B", "A"]


def test_passes_through_single_value():
    assert parse_accounts(["Schwab/Personal"]) == ["Schwab/Personal"]


def test_passes_through_multi_value():
    assert parse_accounts(["A", "B", "C"]) == ["A", "B", "C"]

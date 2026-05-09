from net_alpha.brokers.registry import detect_broker
from net_alpha.brokers.robinhood import RobinhoodParser
from net_alpha.brokers.schwab import SchwabParser


def test_detect_schwab_from_headers():
    headers = ["Date", "Action", "Symbol", "Description", "Quantity", "Price", "Amount"]
    parser = detect_broker(headers)
    assert isinstance(parser, SchwabParser)


def test_detect_returns_none_for_unknown_headers():
    headers = ["weird", "headers", "no", "broker", "matches"]
    assert detect_broker(headers) is None


def test_detect_robinhood_from_headers():
    headers = [
        "Activity Date",
        "Process Date",
        "Settle Date",
        "Instrument",
        "Description",
        "Trans Code",
        "Quantity",
        "Price",
        "Amount",
    ]
    parser = detect_broker(headers)
    assert isinstance(parser, RobinhoodParser)


def test_robinhood_headers_do_not_false_match_schwab():
    headers = [
        "Activity Date",
        "Process Date",
        "Settle Date",
        "Instrument",
        "Description",
        "Trans Code",
        "Quantity",
        "Price",
        "Amount",
    ]
    parser = detect_broker(headers)
    assert not isinstance(parser, SchwabParser)


def test_schwab_headers_still_resolve_to_schwab_after_robinhood_added():
    headers = ["Date", "Action", "Symbol", "Description", "Quantity", "Price", "Amount"]
    parser = detect_broker(headers)
    assert isinstance(parser, SchwabParser)

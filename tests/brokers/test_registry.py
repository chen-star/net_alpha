from net_alpha.brokers.registry import detect_broker
from net_alpha.brokers.schwab import SchwabParser


def test_detect_schwab_from_headers():
    headers = ["Date", "Action", "Symbol", "Description", "Quantity", "Price", "Amount"]
    parser = detect_broker(headers)
    assert isinstance(parser, SchwabParser)


def test_detect_returns_none_for_unknown_headers():
    headers = ["weird", "headers", "no", "broker", "matches"]
    assert detect_broker(headers) is None

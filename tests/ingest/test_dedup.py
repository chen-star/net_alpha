from datetime import date

from net_alpha.ingest.dedup import filter_new
from net_alpha.models.domain import Trade


def _t(qty=10):
    return Trade(
        account="schwab/personal",
        date=date(2024, 1, 1),
        ticker="TSLA",
        action="Buy",
        quantity=qty,
        cost_basis=2000.0,
    )


def test_filter_new_removes_known_keys():
    a, b = _t(10), _t(11)
    known = {a.compute_natural_key()}
    assert filter_new([a, b], known) == [b]


def test_filter_new_empty_known_returns_all():
    a, b = _t(10), _t(11)
    assert filter_new([a, b], set()) == [a, b]

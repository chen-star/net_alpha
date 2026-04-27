from datetime import date

from net_alpha.audit.provenance import (
    CashRef,
    NetContributedRef,
    Period,
    RealizedPLRef,
    UnrealizedPLRef,
    WashImpactRef,
    decode_metric_ref,
    encode_metric_ref,
)


def test_realized_ref_round_trip():
    ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=1,
        symbol="AAPL",
    )
    encoded = encode_metric_ref(ref)
    decoded = decode_metric_ref(encoded)
    assert decoded == ref
    assert isinstance(decoded, RealizedPLRef)


def test_unrealized_ref_round_trip():
    ref = UnrealizedPLRef(kind="unrealized_pl", account_id=None, symbol=None)
    assert decode_metric_ref(encode_metric_ref(ref)) == ref


def test_wash_impact_ref_round_trip():
    ref = WashImpactRef(
        kind="wash_impact",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=2,
    )
    assert decode_metric_ref(encode_metric_ref(ref)) == ref


def test_cash_ref_round_trip():
    ref = CashRef(kind="cash", account_id=None)
    assert decode_metric_ref(encode_metric_ref(ref)) == ref


def test_net_contributed_ref_round_trip():
    ref = NetContributedRef(
        kind="net_contributed",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=None,
    )
    assert decode_metric_ref(encode_metric_ref(ref)) == ref


def test_decode_rejects_garbage():
    import pytest

    with pytest.raises(ValueError):
        decode_metric_ref("not-a-valid-encoding")

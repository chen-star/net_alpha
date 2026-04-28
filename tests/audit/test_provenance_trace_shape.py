from datetime import date

from net_alpha.audit.provenance import (
    AppliedAdjustment,
    ContributingTrade,
    ProvenanceTrace,
)


def test_provenance_trace_serializes():
    trace = ProvenanceTrace(
        metric_label="YTD 2026 Realized P/L · AAPL",
        total=702.54,
        trades=[
            ContributingTrade(
                trade_id="t1",
                trade_date=date(2026, 1, 15),
                account="Schwab/Tax",
                action="Sell",
                quantity=10.0,
                amount=1500.0,
                symbol="AAPL",
                import_id=1,
            )
        ],
        adjustments=[
            AppliedAdjustment(
                violation_id="v1",
                loss_trade_id="t1",
                replacement_trade_id="t2",
                rolled_amount=120.0,
                confidence="Confirmed",
            )
        ],
    )
    dumped = trace.model_dump()
    assert dumped["metric_label"].startswith("YTD")
    assert len(dumped["trades"]) == 1
    assert dumped["adjustments"][0]["rule_citation"].startswith("IRS Pub 550")

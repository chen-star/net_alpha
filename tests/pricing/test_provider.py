"""Phase 3: Quote exposes previous_close for the Today tile."""

from __future__ import annotations


def test_quote_has_previous_close_field():
    from net_alpha.pricing.provider import Quote

    fields = Quote.model_fields
    assert "previous_close" in fields, f"Quote is missing previous_close; got: {list(fields.keys())}"

import json
from unittest.mock import MagicMock

import pytest

from net_alpha.import_.schema_detection import (
    SchemaMapping,
    _build_prompt,
    detect_schema,
)


def _mock_anthropic_response(mapping: dict) -> MagicMock:
    """Create a mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(mapping))]
    return mock_response


SAMPLE_MAPPING = {
    "date": "Date",
    "ticker": "Symbol",
    "action": "Action",
    "quantity": "Quantity",
    "proceeds": "Amount",
    "cost_basis": "Cost Basis",
    "buy_values": ["Buy", "Reinvest"],
    "sell_values": ["Sell"],
    "option_format": "schwab_human",
}


def test_detect_schema_success():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(SAMPLE_MAPPING)

    headers = ["Date", "Symbol", "Action", "Quantity", "Amount", "Cost Basis"]
    sample_rows = [
        {
            "Date": "2024-10-15",
            "Symbol": "TSLA",
            "Action": "Buy",
            "Quantity": "1.00",
            "Amount": "1.00",
            "Cost Basis": "1.00",
        },
    ]

    result = detect_schema(mock_client, headers, sample_rows, "claude-3-5-haiku-latest")
    assert isinstance(result, SchemaMapping)
    assert result.date == "Date"
    assert result.ticker == "Symbol"
    assert "Buy" in result.buy_values


def test_detect_schema_retry_on_failure():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        Exception("API error"),
        Exception("API error"),
        _mock_anthropic_response(SAMPLE_MAPPING),
    ]

    headers = ["Date", "Symbol", "Action", "Quantity", "Amount"]
    sample_rows = [
        {"Date": "2024-10-15", "Symbol": "TSLA", "Action": "Buy", "Quantity": "1.00", "Amount": "1.00"},
    ]

    result = detect_schema(mock_client, headers, sample_rows, "claude-3-5-haiku-latest", max_retries=3)
    assert result is not None
    assert mock_client.messages.create.call_count == 3


def test_detect_schema_hard_fail_after_retries():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    headers = ["Date", "Symbol"]
    sample_rows = [{"Date": "2024-10-15", "Symbol": "TSLA"}]

    with pytest.raises(RuntimeError, match="Schema detection failed"):
        detect_schema(mock_client, headers, sample_rows, "claude-3-5-haiku-latest", max_retries=3)

    assert mock_client.messages.create.call_count == 3


def test_build_prompt_includes_headers_and_rows():
    headers = ["Date", "Symbol", "Action"]
    rows = [{"Date": "2024-10-15", "Symbol": "TSLA", "Action": "Buy"}]
    prompt = _build_prompt(headers, rows)
    assert "Date" in prompt
    assert "Symbol" in prompt
    assert "TSLA" in prompt


def test_schema_mapping_model():
    mapping = SchemaMapping(**SAMPLE_MAPPING)
    assert mapping.date == "Date"
    assert mapping.option_format == "schwab_human"


def test_schema_mapping_optional_fields():
    minimal = SchemaMapping(
        date="Date",
        ticker="Symbol",
        action="Action",
        quantity="Qty",
        buy_values=["Buy"],
        sell_values=["Sell"],
    )
    assert minimal.proceeds is None
    assert minimal.cost_basis is None
    assert minimal.option_format is None

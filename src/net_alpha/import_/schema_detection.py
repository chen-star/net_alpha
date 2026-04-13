from __future__ import annotations

import json
import time
from typing import Optional

from pydantic import BaseModel


class SchemaMapping(BaseModel):
    """Detected column mapping from a broker CSV."""

    date: str
    ticker: str
    action: str
    quantity: str
    proceeds: Optional[str] = None
    cost_basis: Optional[str] = None
    buy_values: list[str]
    sell_values: list[str]
    option_format: Optional[str] = None


def detect_schema(
    client,
    headers: list[str],
    sample_rows: list[dict[str, str]],
    model: str,
    max_retries: int = 3,
) -> SchemaMapping:
    """Call LLM to detect CSV schema from headers and anonymized sample rows.

    Retries up to max_retries with exponential backoff.
    Raises RuntimeError on final failure.
    """
    prompt = _build_prompt(headers, sample_rows)

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            # Extract JSON from response (handle markdown code blocks)
            text = _extract_json(text)
            data = json.loads(text)
            return SchemaMapping(**data)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s

    raise RuntimeError(
        f"Schema detection failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )


def _build_prompt(
    headers: list[str], sample_rows: list[dict[str, str]]
) -> str:
    """Build the LLM prompt for schema detection."""
    header_str = ", ".join(headers)
    rows_str = "\n".join(
        ", ".join(f"{k}: {v}" for k, v in row.items()) for row in sample_rows
    )

    return f"""Analyze this broker CSV format and return a JSON mapping.

CSV Headers: {header_str}

Sample rows (anonymized):
{rows_str}

Return a JSON object with these fields:
- "date": column name containing trade date
- "ticker": column name containing ticker/symbol
- "action": column name containing buy/sell action
- "quantity": column name containing quantity/shares
- "proceeds": column name containing sale proceeds or total amount (null if not present)
- "cost_basis": column name containing cost basis (null if not present)
- "buy_values": list of values in the action column that mean "buy" (e.g., ["Buy", "Reinvest"])
- "sell_values": list of values in the action column that mean "sell" (e.g., ["Sell"])
- "option_format": if options are present, the format type: "occ_standard", "schwab_human", or "robinhood_human" (null if no options or unknown)

Return ONLY the JSON object, no other text."""


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()

from __future__ import annotations

from datetime import date

from net_alpha.cli.output import DISCLAIMER

_STATIC_ROLE = f"""You are a tax-aware trading assistant for net-alpha, a local wash sale detection tool.

You have deep knowledge of:
- Wash sale rules (IRS Publication 550) and the 30-day wash sale window
- Substantially-identical securities, including ETF pairs (e.g. SPY/VOO/IVV/SPLG are treated as identical)
- Short-term vs long-term capital gains classification (holding period under/over 1 year)
- The three confidence levels: Confirmed (definite wash sale), Probable (likely; CPA review),
  Unclear (ambiguous; flag for professional review)
- FIFO, HIFO, and LIFO lot selection methods and their tax implications

Rules you must follow without exception:
- End every response with exactly: {DISCLAIMER}
- Never recommend specific tax actions — surface data and flag for CPA review
- When tool output is ambiguous or a required ticker has no data, say so clearly rather than guess
- Use plain language; avoid jargon unless the user has demonstrated familiarity
"""


def build_system_prompt(state_snapshot: str) -> str:
    """Assemble the full system prompt: static role + today's date + current state snapshot."""
    return f"{_STATIC_ROLE}\nCurrent date: {date.today().isoformat()}\n\nCurrent portfolio state:\n{state_snapshot}"


def build_state_snapshot(status_output: str, check_output: str) -> str:
    """Format status + check outputs as a concise state block for the system prompt."""
    sections = []
    if status_output.strip():
        sections.append(f"--- Account Status ---\n{status_output.strip()}")
    if check_output.strip():
        sections.append(f"--- Wash Sale Check ---\n{check_output.strip()}")
    return "\n\n".join(sections) if sections else "No data available yet. Trades may not be imported."

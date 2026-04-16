from __future__ import annotations

from collections.abc import Callable
from io import StringIO
from typing import Any

from rich.console import Console


def _capture(module: Any, fn_name: str, **kwargs: Any) -> str:
    """
    Call module.<fn_name>(**kwargs) with a string-capturing Console.

    Patches the module-level `console` for the duration of the call so all
    console.print() output goes into a StringIO buffer. Catches SystemExit
    (raised by typer.Exit) so errors are returned as text, not exceptions.
    """
    buf = StringIO()
    cap = Console(file=buf, highlight=False)
    orig = getattr(module, "console")
    setattr(module, "console", cap)
    try:
        getattr(module, fn_name)(**kwargs)
    except SystemExit:
        pass  # typer.Exit (SystemExit subclass) — error message already captured in buf
    except Exception as e:
        import typer

        if isinstance(e, typer.Exit):
            pass  # typer.Exit is an Exception in some versions — treat same as SystemExit
        else:
            return f"Error: {e}"
    finally:
        setattr(module, "console", orig)
    return buf.getvalue().strip()


def run_status() -> str:
    """Run the status command and return output as plain text."""
    import net_alpha.cli.status as _mod

    return _capture(_mod, "status_command")


def run_check(
    ticker: str | None = None,
    type: str | None = None,
    year: int | None = None,
    quiet: bool = False,
) -> str:
    """Run the check command and return output as plain text."""
    import net_alpha.cli.check as _mod

    return _capture(_mod, "check_command", ticker=ticker, type=type, year=year, quiet=quiet)


def run_simulate_sell(
    ticker: str,
    qty: float,
    price: float | None = None,
) -> str:
    """Run the simulate sell command and return output as plain text."""
    import net_alpha.cli.simulate as _mod

    return _capture(_mod, "sell_command", ticker=ticker, qty=qty, price=price)


def run_rebuys() -> str:
    """Run the rebuys command and return output as plain text."""
    import net_alpha.cli.rebuys as _mod

    return _capture(_mod, "rebuys_command")


def run_report(year: int | None = None, csv: bool = False) -> str:
    """Run the report command and return output as plain text."""
    import net_alpha.cli.report as _mod

    return _capture(_mod, "report_command", year=year, csv=csv, quiet=False)


def run_tax_position(year: int | None = None) -> str:
    """Run the tax-position command and return output as plain text."""
    import net_alpha.cli.tax_position as _mod

    return _capture(_mod, "tax_position_command", year=year)


def execute_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Dispatch a tool call by name and return the output string."""
    dispatch: dict[str, Callable[..., str]] = {
        "run_status": lambda **kw: run_status(),
        "run_check": lambda **kw: run_check(**kw),
        "run_simulate_sell": lambda **kw: run_simulate_sell(**kw),
        "run_rebuys": lambda **kw: run_rebuys(),
        "run_report": lambda **kw: run_report(**kw),
        "run_tax_position": lambda **kw: run_tax_position(**kw),
    }
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    return fn(**tool_input)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "run_status",
        "description": (
            "Show imported data freshness, last scan results, and open rebuy windows. "
            "Use this to get an overview of what data is available."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_check",
        "description": (
            "Scan all trades for wash sale violations. Returns a summary and detail table. "
            "Use this to answer questions about wash sale exposure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Filter results to a single ticker symbol (optional)",
                },
                "type": {
                    "type": "string",
                    "enum": ["equities", "options"],
                    "description": "Filter to equities or options only (optional)",
                },
                "year": {
                    "type": "integer",
                    "description": "Tax year to scan (default: current year)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_simulate_sell",
        "description": (
            "Simulate selling a position and check for wash sale risk. "
            "When price is provided, also shows FIFO/HIFO/LIFO lot selection comparison "
            "and a tax-aware recommendation. Use this to answer 'should I sell X?' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol to simulate selling"},
                "qty": {"type": "number", "description": "Number of shares or contracts"},
                "price": {
                    "type": "number",
                    "description": "Sale price per share (optional — enables dollar impact and lot selection)",
                },
            },
            "required": ["ticker", "qty"],
        },
    },
    {
        "name": "run_rebuys",
        "description": (
            "Show positions currently in their 30-day wash sale window that are safe to rebuy "
            "after the window closes. Use this to answer 'what can I buy back?' questions."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_report",
        "description": (
            "Generate a full wash sale report for a tax year. Returns all violations with "
            "disallowed amounts and adjusted basis information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Tax year (default: current year)"},
                "csv": {"type": "boolean", "description": "Also export a CSV file to the current directory"},
            },
            "required": [],
        },
    },
    {
        "name": "run_tax_position",
        "description": (
            "Show YTD realized gains and losses (short-term and long-term), open lots with "
            "holding periods, and positions approaching the 1-year long-term threshold. "
            "Use this to answer questions about current tax position."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Tax year (default: current year)"},
            },
            "required": [],
        },
    },
]

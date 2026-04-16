from __future__ import annotations

from net_alpha.agent.tools import (
    TOOL_SCHEMAS,
    execute_tool,
    run_check,
    run_rebuys,
    run_report,
    run_simulate_sell,
    run_status,
    run_tax_position,
)

# --- Capture mechanism ---


def test_run_status_captures_output(monkeypatch):
    import net_alpha.cli.status as status_mod

    def fake_status_command():
        status_mod.console.print("STATUS OUTPUT")

    monkeypatch.setattr(status_mod, "status_command", fake_status_command)
    result = run_status()
    assert "STATUS OUTPUT" in result


def test_run_check_captures_output(monkeypatch):
    import net_alpha.cli.check as check_mod

    def fake_check_command(**kwargs):
        check_mod.console.print(f"CHECK ticker={kwargs.get('ticker')}")

    monkeypatch.setattr(check_mod, "check_command", fake_check_command)
    result = run_check(ticker="AAPL")
    assert "CHECK ticker=AAPL" in result


def test_run_check_passes_quiet_param(monkeypatch):
    import net_alpha.cli.check as check_mod

    captured = {}

    def fake_check_command(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(check_mod, "check_command", fake_check_command)
    run_check(quiet=True)
    assert captured["quiet"] is True


def test_run_simulate_sell_captures_output(monkeypatch):
    import net_alpha.cli.simulate as sim_mod

    def fake_sell(**kwargs):
        sim_mod.console.print(f"SELL {kwargs['ticker']} {kwargs['qty']}")

    monkeypatch.setattr(sim_mod, "sell_command", fake_sell)
    result = run_simulate_sell(ticker="TSLA", qty=10.0)
    assert "SELL TSLA 10.0" in result


def test_run_rebuys_captures_output(monkeypatch):
    import net_alpha.cli.rebuys as rebuys_mod

    def fake_rebuys():
        rebuys_mod.console.print("REBUYS OUTPUT")

    monkeypatch.setattr(rebuys_mod, "rebuys_command", fake_rebuys)
    result = run_rebuys()
    assert "REBUYS OUTPUT" in result


def test_run_report_captures_output(monkeypatch):
    import net_alpha.cli.report as report_mod

    def fake_report(**kwargs):
        report_mod.console.print(f"REPORT year={kwargs.get('year')}")

    monkeypatch.setattr(report_mod, "report_command", fake_report)
    result = run_report(year=2026)
    assert "REPORT year=2026" in result


def test_run_tax_position_captures_output(monkeypatch):
    import net_alpha.cli.tax_position as tax_mod

    def fake_tax(**kwargs):
        tax_mod.console.print("TAX POSITION OUTPUT")

    monkeypatch.setattr(tax_mod, "tax_position_command", fake_tax)
    result = run_tax_position()
    assert "TAX POSITION OUTPUT" in result


def test_capture_handles_system_exit(monkeypatch):
    """typer.Exit (SystemExit subclass) should not propagate out of run_* functions."""
    import typer

    import net_alpha.cli.check as check_mod

    def fake_check_command(**kwargs):
        check_mod.console.print("Error: bad input")
        raise typer.Exit(1)

    monkeypatch.setattr(check_mod, "check_command", fake_check_command)
    result = run_check()
    assert "Error: bad input" in result


# --- execute_tool dispatch ---


def test_execute_tool_dispatches_run_status(monkeypatch):
    from net_alpha.agent import tools as tools_mod

    monkeypatch.setattr(tools_mod, "run_status", lambda: "status result")
    assert execute_tool("run_status", {}) == "status result"


def test_execute_tool_dispatches_run_check(monkeypatch):
    from net_alpha.agent import tools as tools_mod

    captured = {}

    def fake_check(ticker=None, type=None, year=None, quiet=False):
        captured.update({"ticker": ticker, "year": year})
        return "check result"

    monkeypatch.setattr(tools_mod, "run_check", fake_check)
    result = execute_tool("run_check", {"ticker": "AAPL", "year": 2026})
    assert result == "check result"
    assert captured["ticker"] == "AAPL"
    assert captured["year"] == 2026


def test_execute_tool_dispatches_run_simulate_sell(monkeypatch):
    from net_alpha.agent import tools as tools_mod

    monkeypatch.setattr(tools_mod, "run_simulate_sell", lambda **kw: "sim result")
    assert execute_tool("run_simulate_sell", {"ticker": "AAPL", "qty": 5.0}) == "sim result"


def test_execute_tool_unknown_name():
    result = execute_tool("nonexistent_tool", {})
    assert "Unknown tool" in result


# --- Schema validity ---


def test_tool_schemas_have_required_fields():
    for schema in TOOL_SCHEMAS:
        assert "name" in schema, f"Missing 'name' in schema: {schema}"
        assert "description" in schema, f"Missing 'description' in schema: {schema}"
        assert "input_schema" in schema, f"Missing 'input_schema' in schema: {schema}"
        assert schema["input_schema"]["type"] == "object"
        assert "properties" in schema["input_schema"]
        assert "required" in schema["input_schema"]


def test_all_schema_names_are_unique():
    names = [s["name"] for s in TOOL_SCHEMAS]
    assert len(names) == len(set(names))


def test_run_import_not_in_schemas():
    """run_import must never be exposed as a tool — file imports are user-only actions."""
    names = [s["name"] for s in TOOL_SCHEMAS]
    assert "run_import" not in names


def test_tool_schema_names():
    names = {s["name"] for s in TOOL_SCHEMAS}
    assert names == {
        "run_status",
        "run_check",
        "run_simulate_sell",
        "run_rebuys",
        "run_report",
        "run_tax_position",
    }

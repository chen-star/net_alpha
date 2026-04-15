from io import StringIO

from rich.console import Console

from net_alpha.cli.output import (
    DISCLAIMER,
    confidence_style,
    format_currency,
    print_disclaimer,
)


def test_disclaimer_text():
    assert "informational only" in DISCLAIMER
    assert "tax professional" in DISCLAIMER


def test_print_disclaimer():
    buf = StringIO()
    console = Console(file=buf, no_color=True)
    print_disclaimer(console)
    output = buf.getvalue()
    assert "informational only" in output


def test_format_currency():
    assert format_currency(1200.0) == "$1,200.00"
    assert format_currency(0.0) == "$0.00"
    assert format_currency(50.5) == "$50.50"
    assert format_currency(1234567.89) == "$1,234,567.89"


def test_format_currency_with_parens():
    assert format_currency(-1200.0) == "($1,200.00)"


def test_confidence_style():
    assert confidence_style("Confirmed") == "bold red"
    assert confidence_style("Probable") == "bold yellow"
    assert confidence_style("Unclear") == "bold blue"
    assert confidence_style("Unknown") == ""


from net_alpha.cli.output import format_currency_colored, print_hint


def test_format_currency_colored_positive():
    result = format_currency_colored(1200.0)
    assert "[green]" in result
    assert "$1,200.00" in result


def test_format_currency_colored_negative():
    result = format_currency_colored(-500.0)
    assert "[red]" in result
    assert "($500.00)" in result


def test_format_currency_colored_zero():
    result = format_currency_colored(0.0)
    assert "[green]" not in result
    assert "[red]" not in result
    assert "$0.00" in result


def test_print_hint():
    from io import StringIO
    from rich.console import Console
    buf = StringIO()
    console = Console(file=buf, no_color=True)
    print_hint(console, "Run net-alpha check to scan")
    output = buf.getvalue()
    assert "Run net-alpha check to scan" in output

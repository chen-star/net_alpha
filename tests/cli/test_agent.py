from __future__ import annotations

from net_alpha.cli.agent import _route_local


def test_route_local_exit_commands():
    assert _route_local("exit") == "__exit__"
    assert _route_local("quit") == "__exit__"
    assert _route_local("q") == "__exit__"


def test_route_local_exit_case_insensitive():
    assert _route_local("EXIT") == "__exit__"
    assert _route_local("Quit") == "__exit__"


def test_route_local_help_returns_help_text():
    result = _route_local("help")
    assert result is not None
    assert "net-alpha agent" in result


def test_route_local_unknown_returns_none():
    assert _route_local("do I have wash sales?") is None
    assert _route_local("check AAPL") is None


def test_route_local_empty_returns_none():
    assert _route_local("") is None
    assert _route_local("   ") is None


def test_route_local_passthrough_prefix():
    """!<command> passthrough is NOT handled by _route_local — returns None so REPL handles it."""
    # The REPL itself handles ! prefix; _route_local only handles pure local commands
    assert _route_local("!net-alpha status") is None

import pytest
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    yield


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def schwab_csv(tmp_path):
    p = tmp_path / "schwab.csv"
    p.write_text(
        "Date,Action,Symbol,Quantity,Price,Amount\n"
        "06/15/2024,Buy,TSLA,10,$200.00,$-2000.00\n"
        "08/01/2024,Sell,TSLA,10,$180.00,$1800.00\n"
        "08/10/2024,Buy,TSLA,10,$170.00,$-1700.00\n"
    )
    return str(p)


def test_default_command_imports_and_renders(runner, schwab_csv):
    from net_alpha.cli.app import app

    res = runner.invoke(app, [schwab_csv, "--account", "personal"])
    assert res.exit_code == 0, res.stdout + res.stderr
    assert "Imported" in res.stdout
    assert "informational" in res.stdout.lower()


def test_default_requires_account(runner, schwab_csv):
    from net_alpha.cli.app import app

    res = runner.invoke(app, [schwab_csv])
    assert res.exit_code != 0


def test_imports_subcommand_lists_one_row(runner, schwab_csv):
    from net_alpha.cli.app import app

    runner.invoke(app, [schwab_csv, "--account", "personal"])
    res = runner.invoke(app, ["imports"])
    assert res.exit_code == 0
    assert "schwab.csv" in res.stdout


def test_unsupported_broker_exits_2(runner, tmp_path):
    from net_alpha.cli.app import app

    bad = tmp_path / "weird.csv"
    bad.write_text("foo,bar\n1,2\n")
    res = runner.invoke(app, [str(bad), "--account", "x"])
    assert res.exit_code == 2


def test_double_import_reports_duplicates(runner, schwab_csv):
    from net_alpha.cli.app import app

    runner.invoke(app, [schwab_csv, "--account", "personal"])
    res = runner.invoke(app, [schwab_csv, "--account", "personal"])
    assert res.exit_code == 0
    assert "0 new" in res.stdout or "duplicates" in res.stdout

from unittest.mock import patch

from typer.testing import CliRunner

from net_alpha.cli.app import app

runner = CliRunner()


def test_install_subcommand_calls_control_install():
    with patch("net_alpha.service.control.install") as inst:
        result = runner.invoke(app, ["service", "install"])
    assert result.exit_code == 0, result.output
    inst.assert_called_once_with(port=8765)


def test_install_with_custom_port():
    with patch("net_alpha.service.control.install") as inst:
        result = runner.invoke(app, ["service", "install", "--port", "9000"])
    assert result.exit_code == 0
    inst.assert_called_once_with(port=9000)


def test_stop_calls_control_stop():
    with patch("net_alpha.service.control.stop") as st:
        result = runner.invoke(app, ["service", "stop"])
    assert result.exit_code == 0
    st.assert_called_once()


def test_status_human_output():
    from net_alpha.service import control as ctrl

    fake = ctrl.Status(installed=True, running=True, paused=False, pid=42, disabled=False)
    with patch("net_alpha.service.control.status", return_value=fake):
        result = runner.invoke(app, ["service", "status"])
    assert result.exit_code == 0
    assert "Running" in result.output
    assert "pid 42" in result.output


def test_status_json_output():
    from net_alpha.service import control as ctrl

    fake = ctrl.Status(installed=True, running=False, paused=False, pid=None, disabled=True)
    with patch("net_alpha.service.control.status", return_value=fake):
        result = runner.invoke(app, ["service", "status", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data == {"installed": True, "running": False, "paused": False, "pid": None, "disabled": True}

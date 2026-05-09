import os
from pathlib import Path
from unittest.mock import patch

from net_alpha.service import control, paths


def _stub_binary(tmp_path: Path) -> Path:
    binary = tmp_path / "fake-binary" / "net-alpha"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/bash\necho fake\n")
    binary.chmod(0o755)
    return binary


def test_install_writes_plist_wrapper_and_sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_provision_service_venv", lambda: str(binary))
    with patch.object(control, "_launchctl_reload") as load:
        control.install(port=8765)
    assert paths.plist_file().exists()
    assert paths.wrapper_script().exists()
    assert paths.sandbox_profile().exists()
    load.assert_called_once()


def test_install_makes_wrapper_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_provision_service_venv", lambda: str(binary))
    with patch.object(control, "_launchctl_reload"):
        control.install(port=8765)
    mode = paths.wrapper_script().stat().st_mode
    assert mode & 0o111  # executable bit set


def test_install_clears_disabled_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.disabled_flag().write_text("stale")
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_provision_service_venv", lambda: str(binary))
    with patch.object(control, "_launchctl_reload"):
        control.install(port=8765)
    assert not paths.disabled_flag().exists()


def test_install_is_idempotent_when_service_already_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_provision_service_venv", lambda: str(binary))
    with patch.object(control, "_launchctl_bootout") as bo, patch.object(control, "_launchctl_bootstrap") as bs:
        control.install(port=8765)
    # Reload bootouts first so a stale plist doesn't make bootstrap exit 5.
    bo.assert_called_once()
    bs.assert_called_once()


def test_install_wraps_entry_point_inside_service_venv(tmp_path, monkeypatch):
    """The wrapper script must point at ~/.net_alpha/venv/bin/net-alpha — the
    runtime venv lives outside ~/Documents so launchd's TCC identity can read it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_provision_service_venv", lambda: str(binary))
    with patch.object(control, "_launchctl_reload"):
        control.install(port=8765)
    text = paths.wrapper_script().read_text()
    assert str(binary) in text


def test_provision_service_venv_installs_with_ui_extras(tmp_path, monkeypatch):
    """The runtime venv must include the [ui] extras (yfinance, fastapi, …) —
    they live in pyproject.toml's optional-dependencies, but the always-on
    service is a web app and won't import without them."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    project_source = tmp_path / "wash-alpha"
    project_source.mkdir()
    (project_source / "pyproject.toml").write_text("[project]\nname = 'wash-alpha'\n")
    monkeypatch.setattr(control, "_resolve_project_source", lambda: project_source)
    fake_run = MagicMock()
    monkeypatch.setattr(control.subprocess, "run", fake_run)
    control._provision_service_venv()
    pip_install_args = fake_run.call_args_list[1].args[0]
    assert pip_install_args[-1] == f"{project_source}[ui]"


def test_provision_service_venv_clears_existing_venv(tmp_path, monkeypatch):
    """`uv venv` refuses to overwrite an existing venv — re-running install
    must pass --clear so the second invocation doesn't fail with
    `A virtual environment already exists at ...`."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    project_source = tmp_path / "wash-alpha"
    project_source.mkdir()
    (project_source / "pyproject.toml").write_text("[project]\nname = 'wash-alpha'\n")
    monkeypatch.setattr(control, "_resolve_project_source", lambda: project_source)
    fake_run = MagicMock()
    monkeypatch.setattr(control.subprocess, "run", fake_run)
    control._provision_service_venv()
    venv_args = fake_run.call_args_list[0].args[0]
    assert "--clear" in venv_args


def test_uninstall_removes_plist_wrapper_sandbox_and_venv(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.plist_file().write_text("<plist/>")
    paths.wrapper_script().write_text("#!/bin/bash\n")
    paths.sandbox_profile().write_text("(version 1)")
    paths.service_venv().mkdir(parents=True, exist_ok=True)
    (paths.service_venv() / "marker").write_text("x")
    with patch.object(control, "_launchctl_bootout") as bo:
        control.uninstall()
    bo.assert_called_once()
    assert not paths.plist_file().exists()
    assert not paths.wrapper_script().exists()
    assert not paths.sandbox_profile().exists()
    assert not paths.service_venv().exists()


def test_uninstall_leaves_data_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    db = paths.net_alpha_home() / "net_alpha.db"
    db.write_text("DATA")
    with patch.object(control, "_launchctl_bootout"):
        control.uninstall()
    assert db.exists()
    assert db.read_text() == "DATA"


def test_start_clears_disabled_flag_and_reloads(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.disabled_flag().write_text("x")
    paths.plist_file().write_text("<plist/>")
    with patch.object(control, "_launchctl_reload") as load:
        control.start()
    assert not paths.disabled_flag().exists()
    load.assert_called_once()


def test_start_raises_if_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    import pytest

    with pytest.raises(control.NotInstalled):
        control.start()


def test_stop_writes_disabled_flag_and_calls_bootout(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    with patch.object(control, "_launchctl_bootout") as bo:
        control.stop(reason="user requested")
    assert paths.disabled_flag().exists()
    assert "user requested" in paths.disabled_flag().read_text()
    bo.assert_called_once()


def test_restart_when_running_bootouts_then_bootstraps(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.plist_file().write_text("<plist/>")
    with patch.object(control, "_launchctl_bootout") as bo, patch.object(control, "_launchctl_bootstrap") as bs:
        control.restart()
    bo.assert_called_once()
    bs.assert_called_once()


def test_launchctl_reload_bootouts_then_bootstraps():
    with patch.object(control, "_launchctl_bootout") as bo, patch.object(control, "_launchctl_bootstrap") as bs:
        control._launchctl_reload()
    bo.assert_called_once()
    bs.assert_called_once()


def test_restart_refuses_when_disabled_flag_present(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.plist_file().write_text("<plist/>")
    paths.disabled_flag().write_text("x")
    import pytest

    with pytest.raises(control.ServiceStopped):
        control.restart()


def test_status_uninstalled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    s = control.status()
    assert s.installed is False
    assert s.running is False
    assert s.disabled is False
    assert s.pid is None


def test_status_installed_but_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.plist_file().write_text("<plist/>")
    paths.disabled_flag().write_text("x")
    with patch.object(control, "_launchctl_print", return_value=""):
        s = control.status()
    assert s.installed is True
    assert s.disabled is True
    assert s.running is False


def test_status_installed_and_running(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.plist_file().write_text("<plist/>")
    paths.pid_file().write_text(str(os.getpid()))
    fake_print = "state = running\n\tpid = 12345\n"
    with patch.object(control, "_launchctl_print", return_value=fake_print):
        s = control.status()
    assert s.installed is True
    assert s.running is True
    assert s.pid == 12345


def test_pause_in_process_marks_state_and_pauses_scheduler():
    from unittest.mock import MagicMock as MM

    from net_alpha.service.state import ServiceState

    state = ServiceState()
    sched = MM()
    control.pause_in_process(state=state, scheduler=sched)
    assert state.paused is True
    sched.pause.assert_called_once()


def test_resume_in_process_unmarks_state_and_resumes_scheduler():
    from unittest.mock import MagicMock as MM

    from net_alpha.service.state import ServiceState

    state = ServiceState()
    state.pause()
    sched = MM()
    control.resume_in_process(state=state, scheduler=sched)
    assert state.paused is False
    sched.resume.assert_called_once()


def test_pause_via_http_when_service_running(monkeypatch):
    """When the service is running, control.pause() POSTs to /settings/service/control."""
    from unittest.mock import MagicMock as MM

    fake_post = MM(return_value=MM(status_code=200))
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_post)
    monkeypatch.setattr(control, "_status_running", lambda: True)
    control.pause()
    fake_post.assert_called_once()


def test_resume_via_http_when_service_running(monkeypatch):
    from unittest.mock import MagicMock as MM

    fake_post = MM(return_value=MM(status_code=200))
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_post)
    monkeypatch.setattr(control, "_status_running", lambda: True)
    control.resume()
    fake_post.assert_called_once()


def test_pause_raises_not_installed_when_service_not_running(monkeypatch):
    import pytest

    monkeypatch.setattr(control, "_status_running", lambda: False)
    with pytest.raises(control.NotInstalled):
        control.pause()


def test_install_raises_helpful_error_when_uv_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_provision_service_venv", lambda: str(binary))
    monkeypatch.setattr(control, "_uv_available", lambda: False)
    import pytest

    with pytest.raises(control.MissingUv):
        control.install(port=8765)


def test_logs_prints_last_n_lines(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.log_file().write_text("\n".join(f"line {i}" for i in range(100)) + "\n")
    control.logs(follow=False, lines=5)
    out = capsys.readouterr().out
    assert "line 95" in out
    assert "line 99" in out


def test_logs_when_no_log_file_prints_friendly_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    # no log file
    control.logs(follow=False, lines=5)
    err = capsys.readouterr().err
    assert "No service log" in err

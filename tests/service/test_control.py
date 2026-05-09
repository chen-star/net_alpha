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
    monkeypatch.setattr(control, "_resolve_binary", lambda: str(binary))
    with patch.object(control, "_launchctl_bootstrap") as load:
        control.install(port=8765)
    assert paths.plist_file().exists()
    assert paths.wrapper_script().exists()
    assert paths.sandbox_profile().exists()
    load.assert_called_once()


def test_install_makes_wrapper_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_resolve_binary", lambda: str(binary))
    with patch.object(control, "_launchctl_bootstrap"):
        control.install(port=8765)
    mode = paths.wrapper_script().stat().st_mode
    assert mode & 0o111  # executable bit set


def test_install_clears_disabled_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.disabled_flag().write_text("stale")
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_resolve_binary", lambda: str(binary))
    with patch.object(control, "_launchctl_bootstrap"):
        control.install(port=8765)
    assert not paths.disabled_flag().exists()


def test_uninstall_removes_plist_wrapper_and_sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.plist_file().write_text("<plist/>")
    paths.wrapper_script().write_text("#!/bin/bash\n")
    paths.sandbox_profile().write_text("(version 1)")
    with patch.object(control, "_launchctl_bootout") as bo:
        control.uninstall()
    bo.assert_called_once()
    assert not paths.plist_file().exists()
    assert not paths.wrapper_script().exists()
    assert not paths.sandbox_profile().exists()


def test_uninstall_leaves_data_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    db = paths.net_alpha_home() / "net_alpha.db"
    db.write_text("DATA")
    with patch.object(control, "_launchctl_bootout"):
        control.uninstall()
    assert db.exists()
    assert db.read_text() == "DATA"


def test_start_clears_disabled_flag_and_calls_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.disabled_flag().write_text("x")
    paths.plist_file().write_text("<plist/>")
    with patch.object(control, "_launchctl_bootstrap") as bs:
        control.start()
    assert not paths.disabled_flag().exists()
    bs.assert_called_once()


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

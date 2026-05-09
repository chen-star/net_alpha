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

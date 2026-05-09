"""End-to-end Phase 1: install → stop → start → restart → uninstall artifact lifecycle."""

import plistlib
from pathlib import Path
from unittest.mock import patch

import pytest

from net_alpha.service import control, paths


def _stub_binary(tmp_path: Path) -> Path:
    """Create a fake net-alpha binary in tmp_path."""
    binary = tmp_path / "bin" / "net-alpha"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/bash\necho fake\n")
    binary.chmod(0o755)
    return binary


def test_full_lifecycle_artifacts(tmp_path, monkeypatch):
    """Test the complete service lifecycle: install → stop → start → restart → uninstall."""
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_resolve_binary", lambda: str(binary))

    with patch.object(control, "_launchctl_bootstrap"), patch.object(control, "_launchctl_bootout"):
        # Step 1: install
        control.install(port=8765)
        assert paths.plist_file().exists(), "plist should exist after install"
        assert paths.wrapper_script().exists(), "wrapper should exist after install"
        assert paths.sandbox_profile().exists(), "sandbox profile should exist after install"
        assert not paths.disabled_flag().exists(), "disabled flag should not exist after install"

        # Verify plist content
        parsed = plistlib.loads(paths.plist_file().read_bytes())
        assert parsed["Label"] == "com.netalpha.service"
        assert parsed["ProgramArguments"][0] == str(paths.wrapper_script())

        # Verify wrapper script contains disabled flag check
        wrapper_text = paths.wrapper_script().read_text()
        assert "disabled" in wrapper_text, "wrapper should reference disabled flag"

        # Step 2: stop
        control.stop(reason="integration test")
        assert paths.disabled_flag().exists(), "disabled flag should exist after stop"
        assert "integration test" in paths.disabled_flag().read_text()

        # Verify restart on stopped service raises
        with pytest.raises(control.ServiceStopped):
            control.restart()

        # Step 3: start
        control.start()
        assert not paths.disabled_flag().exists(), "disabled flag should be cleared after start"

        # Step 4: restart (while running)
        control.restart()
        # No exception; restart succeeds on a running service

        # Step 5: uninstall
        control.uninstall()
        assert not paths.plist_file().exists(), "plist should be removed after uninstall"
        assert not paths.wrapper_script().exists(), "wrapper should be removed after uninstall"
        assert not paths.sandbox_profile().exists(), "sandbox should be removed after uninstall"


def test_install_port_embedded_in_artifacts(tmp_path, monkeypatch):
    """Verify that the specified port is embedded in sandbox profile."""
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_resolve_binary", lambda: str(binary))

    with patch.object(control, "_launchctl_bootstrap"):
        control.install(port=9999)

    # Port should appear in sandbox profile (allows network access on that port)
    sandbox_text = paths.sandbox_profile().read_text()
    assert "9999" in sandbox_text, "port should be in sandbox profile"


def test_uninstall_preserves_database(tmp_path, monkeypatch):
    """Verify that uninstall removes only service artifacts, not user data."""
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()

    # Create mock database file
    db = paths.net_alpha_home() / "net_alpha.db"
    db.write_text("MOCK DATABASE CONTENT")

    # Create service artifacts
    paths.plist_file().write_text("<plist/>")
    paths.wrapper_script().write_text("#!/bin/bash\n")
    paths.sandbox_profile().write_text("(version 1)")

    with patch.object(control, "_launchctl_bootout"):
        control.uninstall()

    # Service artifacts gone
    assert not paths.plist_file().exists()
    assert not paths.wrapper_script().exists()
    assert not paths.sandbox_profile().exists()

    # User data preserved
    assert db.exists()
    assert db.read_text() == "MOCK DATABASE CONTENT"


def test_status_after_lifecycle(tmp_path, monkeypatch):
    """Verify status reports are accurate through lifecycle transitions."""
    monkeypatch.setenv("HOME", str(tmp_path))
    binary = _stub_binary(tmp_path)
    monkeypatch.setattr(control, "_resolve_binary", lambda: str(binary))

    # Before install: uninstalled
    s = control.status()
    assert s.installed is False
    assert s.running is False
    assert s.disabled is False

    with patch.object(control, "_launchctl_bootstrap"), patch.object(control, "_launchctl_bootout"):
        # After install: installed and running
        control.install(port=8765)
        with patch.object(control, "_launchctl_print", return_value="state = running\n\tpid = 12345\n"):
            s = control.status()
        assert s.installed is True
        assert s.running is True
        assert s.disabled is False

        # After stop: installed but disabled
        control.stop(reason="test")
        with patch.object(control, "_launchctl_print", return_value=""):
            s = control.status()
        assert s.installed is True
        assert s.running is False
        assert s.disabled is True

        # After start: installed and running again
        control.start()
        with patch.object(control, "_launchctl_print", return_value="state = running\n\tpid = 12346\n"):
            s = control.status()
        assert s.installed is True
        assert s.running is True
        assert s.disabled is False

        # After uninstall: uninstalled
        control.uninstall()
        s = control.status()
        assert s.installed is False
        assert s.running is False
        assert s.disabled is False


def test_scheduler_starts_and_runs_price_refresh_synchronously(tmp_path, monkeypatch):
    """Run price_refresh through the runner, end-to-end, in a sync test."""
    from unittest.mock import MagicMock as MM

    from net_alpha.service.jobs.price_refresh import run_price_refresh
    from net_alpha.service.jobs.runner import run_job
    from net_alpha.service.state import ServiceState

    monkeypatch.setenv("HOME", str(tmp_path))

    repo = MM()
    repo.distinct_held_tickers.return_value = ["AAPL"]
    repo.distinct_target_tickers.return_value = []
    pricing = MM()
    state = ServiceState()

    payload = run_job(
        job_name="price_refresh",
        fn=lambda: run_price_refresh(repo=repo, pricing=pricing),
        state=state,
        repo=repo,
    )
    assert payload == {"symbols": 1}
    assert state.last_run("price_refresh").status == "ok"
    pricing.refresh.assert_called_once_with(["AAPL"])


def test_full_phase4_sync_smoke(tmp_path, monkeypatch):
    """End-to-end smoke: run both jobs once each via the runner, verify they record."""
    from datetime import date
    from unittest.mock import MagicMock as MM

    from net_alpha.service.jobs.price_refresh import run_price_refresh
    from net_alpha.service.jobs.runner import run_job
    from net_alpha.service.jobs.washsale_watch import run_washsale_watch
    from net_alpha.service.state import ServiceState

    monkeypatch.setenv("HOME", str(tmp_path))

    repo = MM()
    repo.distinct_held_tickers.return_value = ["SPY"]
    repo.distinct_target_tickers.return_value = []
    repo.list_position_targets.return_value = []
    pricing = MM()
    state = ServiceState()

    # price_refresh
    run_job(
        job_name="price_refresh",
        fn=lambda: run_price_refresh(repo=repo, pricing=pricing),
        state=state,
        repo=repo,
    )
    # washsale_watch
    run_job(
        job_name="washsale_watch",
        fn=lambda: run_washsale_watch(repo=repo, today=date(2026, 5, 1)),
        state=state,
        repo=repo,
    )

    assert state.last_run("price_refresh").status == "ok"
    assert state.last_run("washsale_watch").status == "ok"
    assert repo.record_service_run.call_count == 2

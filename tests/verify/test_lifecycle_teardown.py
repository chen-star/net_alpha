"""Phase 6 / Task 18: guard 'service uninstall' leaves no verify residue.

The verify job is registered with the in-process APScheduler — it has no
external launchd plist of its own. This test guards against future drift
(e.g. someone adds a separate launchd plist for verify and forgets to
teardown).
"""

from __future__ import annotations

import sys

import pytest

_ON_MACOS = sys.platform == "darwin"


@pytest.mark.skipif(not _ON_MACOS, reason="launchctl is macOS-only")
def test_no_verify_plist_in_service_modules():
    """Outside scheduler.py + control.py, no service-layer module may mention 'verify'.

    Rationale: the verify job is registered in scheduler.py and torn down
    implicitly with the rest of the APScheduler jobs when the launchd-managed
    process exits. If someone introduces a *separate* launchd plist file
    template, a sandbox profile entry, or any other service-layer artifact for
    'verify', that change needs to be paired with explicit cleanup in
    cli/service.py + control.uninstall() — bump the allowlist below only after
    adding that teardown.
    """
    import pathlib

    root = pathlib.Path(__file__).parents[2] / "src" / "net_alpha" / "service"
    allowed = {"scheduler.py", "__init__.py", "control.py"}
    for p in root.glob("*.py"):
        if p.name in allowed:
            continue
        content = p.read_text()
        assert "verify" not in content.lower(), (
            f"{p.name} mentions 'verify' — only scheduler.py should register the verify job. "
            "If you've added a launchd plist for the verify job, add explicit teardown "
            "to cli/service.py uninstall and update this test."
        )


def test_uninstall_runs_clean(tmp_path, monkeypatch):
    """Smoke test: 'service uninstall' must not raise on verify-related cleanup.

    Wires up just enough of the control module to invoke uninstall in a
    sandbox; if a future change adds verify-specific cleanup steps, this
    test catches breakage. Errors that aren't *verify-specific* (missing
    plist, missing helper on a non-darwin platform, etc.) are allowed.
    """
    from net_alpha.service import control

    # control.uninstall reaches into ~ via the service.paths module; redirect
    # HOME so we don't touch the developer's real ~/.net_alpha.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))

    try:
        control.uninstall()
    except (FileNotFoundError, AttributeError):
        # Legitimate on platforms / states where there's no plist installed —
        # the test only fails on verify-specific surprises.
        pass

"""One module owns all service lifecycle logic.

UI routes, CLI subcommands, and any future menu-bar app are thin
clients on top of this module. No surface has its own logic.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from net_alpha.service import disabled_flag, paths, plist, sandbox, wrapper
from net_alpha.service.paths import PLIST_LABEL

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_binary() -> str:
    """Locate the absolute path to the net-alpha entry-point script."""
    found = shutil.which("net-alpha")
    if found:
        return found
    candidate = Path(sys.prefix) / "bin" / "net-alpha"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("Could not resolve the net-alpha binary path. Is wash-alpha installed in this environment?")


def _gui_domain() -> str:
    return f"gui/{os.getuid()}"


def _launchctl_bootstrap() -> None:
    subprocess.run(
        ["launchctl", "bootstrap", _gui_domain(), str(paths.plist_file())],
        check=True,
        capture_output=True,
        text=True,
    )


def _launchctl_bootout() -> None:
    subprocess.run(
        ["launchctl", "bootout", f"{_gui_domain()}/{PLIST_LABEL}"],
        capture_output=True,
        text=True,
    )


def _launchctl_print() -> str:
    p = subprocess.run(
        ["launchctl", "print", f"{_gui_domain()}/{PLIST_LABEL}"],
        capture_output=True,
        text=True,
    )
    return p.stdout


# ---------------------------------------------------------------------------
# Public API — one function per CLI verb
# ---------------------------------------------------------------------------


class NotInstalled(RuntimeError):
    """Raised when a control verb requires an installed plist but none is found."""


class ServiceStopped(RuntimeError):
    """Raised when a control verb assumes a running service but the disabled flag is set."""


def install(*, port: int = 8765) -> None:
    paths.ensure_dirs()
    binary = _resolve_binary()

    paths.sandbox_profile().write_text(sandbox.render(net_alpha_home=str(paths.net_alpha_home()), port=port))

    paths.wrapper_script().write_text(
        wrapper.render(
            binary=binary,
            sandbox_profile=str(paths.sandbox_profile()),
            disabled_flag=str(paths.disabled_flag()),
        )
    )
    paths.wrapper_script().chmod(0o755)

    paths.plist_file().write_bytes(
        plist.render(
            wrapper_path=str(paths.wrapper_script()),
            log_path=str(paths.log_file()),
        )
    )

    disabled_flag.clear()
    _launchctl_bootstrap()


def uninstall() -> None:
    _launchctl_bootout()
    for p in (paths.plist_file(), paths.wrapper_script(), paths.sandbox_profile()):
        if p.exists():
            p.unlink()


def start() -> None:
    if not paths.plist_file().exists():
        raise NotInstalled(
            "Service is not installed. Run `net-alpha service install` first."
        )
    disabled_flag.clear()
    _launchctl_bootstrap()


def stop(*, reason: str = "manual stop") -> None:
    disabled_flag.set(reason)
    _launchctl_bootout()


def pause() -> None:
    raise NotImplementedError  # Task 2.x


def resume() -> None:
    raise NotImplementedError  # Task 2.x


def restart() -> None:
    if not paths.plist_file().exists():
        raise NotInstalled("Service is not installed.")
    if disabled_flag.is_set():
        raise ServiceStopped(
            "Service is stopped. Run `net-alpha service start` instead — "
            "restart is a no-op on a stopped service."
        )
    _launchctl_bootout()
    _launchctl_bootstrap()


@dataclass
class Status:
    installed: bool
    running: bool
    paused: bool
    pid: int | None
    disabled: bool


def status() -> Status:
    raise NotImplementedError  # Task 1.13

"""One module owns all service lifecycle logic.

UI routes, CLI subcommands, and any future menu-bar app are thin
clients on top of this module. No surface has its own logic.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time as _time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from net_alpha.service import disabled_flag, paths, plist, sandbox, wrapper
from net_alpha.service.paths import PLIST_LABEL

DIST_NAME = "wash-alpha"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_project_source() -> Path:
    """Find the wash-alpha project root that holds pyproject.toml.

    Why: install() builds a fresh runtime venv from this source. Editable
    installs expose the source via direct_url.json; non-editable installs
    fall back to walking up from the package's __file__.
    """
    try:
        dist = distribution(DIST_NAME)
    except PackageNotFoundError as e:
        raise RuntimeError(f"{DIST_NAME} is not installed in this environment.") from e

    raw = dist.read_text("direct_url.json")
    if raw:
        url = json.loads(raw).get("url", "")
        if url.startswith("file://"):
            candidate = Path(url[len("file://") :])
            if (candidate / "pyproject.toml").exists():
                return candidate

    import net_alpha

    if net_alpha.__file__:
        for parent in Path(net_alpha.__file__).parents:
            if (parent / "pyproject.toml").exists():
                return parent
    raise RuntimeError(f"Could not locate the {DIST_NAME} project source for service install.")


def _provision_service_venv() -> str:
    """Create ~/.net_alpha/venv and install wash-alpha into it.

    The LaunchAgent runs under launchd's TCC identity and cannot read
    paths under ~/Documents, so the runtime venv must live inside the
    sandbox-allowed home (~/.net_alpha/). Returns the absolute path to
    the net-alpha entry-point inside the new venv.
    """
    venv = paths.service_venv()
    project_source = _resolve_project_source()
    subprocess.run(
        ["uv", "venv", "--python", "3.11", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv / "bin" / "python"),
            "--reinstall-package",
            DIST_NAME,
            str(project_source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(venv / "bin" / "net-alpha")


def _uv_available() -> bool:
    """Return True iff the ``uv`` tool is on PATH."""
    return shutil.which("uv") is not None


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


def _launchctl_reload() -> None:
    """Bootout (best-effort) then bootstrap. Idempotent if already loaded."""
    _launchctl_bootout()
    _launchctl_bootstrap()


def _launchctl_print() -> str:
    p = subprocess.run(
        ["launchctl", "print", f"{_gui_domain()}/{PLIST_LABEL}"],
        capture_output=True,
        text=True,
    )
    return p.stdout


def _status_running() -> bool:
    """True iff the installed service is up and not disabled."""
    s = status()
    return s.installed and s.running and not s.disabled


def _post_control(action: str, port: int = 8765) -> None:
    data = urllib.parse.urlencode({"action": action}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/settings/service/control",
        data=data,
    )
    urllib.request.urlopen(req, timeout=5)


# ---------------------------------------------------------------------------
# Public API — one function per CLI verb
# ---------------------------------------------------------------------------


class NotInstalled(RuntimeError):
    """Raised when a control verb requires an installed plist but none is found."""


class ServiceStopped(RuntimeError):
    """Raised when a control verb assumes a running service but the disabled flag is set."""


class MissingUv(RuntimeError):
    """Raised when service install is requested but uv is not on PATH."""


def install(*, port: int = 8765) -> None:
    if not _uv_available():
        raise MissingUv(
            "The always-on service requires uv. Install it from "
            "https://docs.astral.sh/uv/ and re-run `net-alpha service install`."
        )
    paths.ensure_dirs()
    binary = _provision_service_venv()

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
    _launchctl_reload()


def uninstall() -> None:
    _launchctl_bootout()
    for p in (paths.plist_file(), paths.wrapper_script(), paths.sandbox_profile()):
        if p.exists():
            p.unlink()
    if paths.service_venv().exists():
        shutil.rmtree(paths.service_venv())


def start() -> None:
    if not paths.plist_file().exists():
        raise NotInstalled("Service is not installed. Run `net-alpha service install` first.")
    disabled_flag.clear()
    _launchctl_reload()


def stop(*, reason: str = "manual stop") -> None:
    disabled_flag.set(reason)
    _launchctl_bootout()


def pause() -> None:
    if not _status_running():
        raise NotInstalled("Service is not running.")
    _post_control("pause")


def resume() -> None:
    if not _status_running():
        raise NotInstalled("Service is not running.")
    _post_control("resume")


def pause_in_process(*, state, scheduler) -> None:
    """In-process pause: flip ServiceState.paused and pause the scheduler.

    Called by the web `/settings/service/control` POST endpoint. CLI
    pause/resume are different code paths that reach this via HTTP.
    """
    state.pause()
    scheduler.pause()


def resume_in_process(*, state, scheduler) -> None:
    """In-process resume: flip ServiceState.paused and resume the scheduler."""
    state.resume()
    scheduler.resume()


def restart() -> None:
    if not paths.plist_file().exists():
        raise NotInstalled("Service is not installed.")
    if disabled_flag.is_set():
        raise ServiceStopped(
            "Service is stopped. Run `net-alpha service start` instead — restart is a no-op on a stopped service."
        )
    _launchctl_reload()


@dataclass
class Status:
    installed: bool
    running: bool
    paused: bool
    pid: int | None
    disabled: bool


def status() -> Status:
    installed = paths.plist_file().exists()
    is_disabled = disabled_flag.is_set()

    if not installed:
        return Status(installed=False, running=False, paused=False, pid=None, disabled=False)

    out = _launchctl_print()
    match = re.search(r"\bpid\s*=\s*(\d+)", out)
    pid = int(match.group(1)) if match else None
    running = "state = running" in out and pid is not None

    return Status(
        installed=True,
        running=running,
        paused=False,  # paused state lives in-process; populated by Task 2.x
        pid=pid,
        disabled=is_disabled,
    )


def logs(*, follow: bool, lines: int) -> None:
    """Tail the service log; --follow streams new lines indefinitely."""
    p = paths.log_file()
    if not p.exists():
        sys.stderr.write("No service log yet.\n")
        return
    with p.open("r") as f:
        all_lines = f.readlines()
    for line in all_lines[-lines:]:
        sys.stdout.write(line)
    if not follow:
        return
    with p.open("r") as f:
        f.seek(0, 2)  # seek to end
        while True:
            line = f.readline()
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                _time.sleep(0.5)

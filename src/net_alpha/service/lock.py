"""Single-instance lock via a pid file.

Keeps the user from accidentally booting two service processes that
fight over port 18765.
"""

from __future__ import annotations

import errno
import os

from net_alpha.service import paths


class AlreadyRunning(RuntimeError):
    """Raised when another live process holds the lock."""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as e:
        return e.errno != errno.ESRCH
    return True


def acquire() -> None:
    paths.ensure_dirs()
    p = paths.pid_file()
    if p.exists():
        try:
            existing = int(p.read_text().strip())
        except ValueError:
            existing = -1
        if _pid_alive(existing):
            raise AlreadyRunning(f"Another net-alpha service is already running (pid {existing}).")
    p.write_text(str(os.getpid()))


def release() -> None:
    p = paths.pid_file()
    if p.exists():
        p.unlink()

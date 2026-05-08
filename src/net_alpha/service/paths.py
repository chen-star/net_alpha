"""Canonical filesystem paths for the always-on service."""

from __future__ import annotations

import os
from pathlib import Path

PLIST_LABEL = "com.netalpha.service"


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def net_alpha_home() -> Path:
    return home() / ".net_alpha"


def run_dir() -> Path:
    return net_alpha_home() / "run"


def bin_dir() -> Path:
    return net_alpha_home() / "bin"


def logs_dir() -> Path:
    return net_alpha_home() / "logs"


def launch_agents_dir() -> Path:
    return home() / "Library" / "LaunchAgents"


def pid_file() -> Path:
    return run_dir() / "service.pid"


def disabled_flag() -> Path:
    return run_dir() / "disabled"


def plist_file() -> Path:
    return launch_agents_dir() / f"{PLIST_LABEL}.plist"


def wrapper_script() -> Path:
    return bin_dir() / "net-alpha-wrap"


def sandbox_profile() -> Path:
    return run_dir() / "sandbox.sb"


def log_file() -> Path:
    return logs_dir() / "service.log"


def ensure_dirs() -> None:
    for d in (run_dir(), bin_dir(), logs_dir(), launch_agents_dir()):
        d.mkdir(parents=True, exist_ok=True)

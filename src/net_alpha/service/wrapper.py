"""Render the launchd wrapper shell script.

The wrapper is what launchd actually invokes. It checks for the
disabled-flag latch and exits 0 if present (this is what makes Stop
survive reboots), then exec()s the sandbox-wrapped service binary.
"""

from __future__ import annotations

_TEMPLATE = """#!/bin/bash
set -euo pipefail

# Disabled-flag latch — when present, the user has stopped the service.
# Exit cleanly so launchd does not flag a crash.
if [ -f "{disabled_flag}" ]; then
    exit 0
fi

exec sandbox-exec -f "{sandbox_profile}" "{binary}" service run
"""


def render(*, binary: str, sandbox_profile: str, disabled_flag: str) -> str:
    """Return the bash script text for the launchd wrapper."""
    return _TEMPLATE.format(
        binary=binary,
        sandbox_profile=sandbox_profile,
        disabled_flag=disabled_flag,
    )

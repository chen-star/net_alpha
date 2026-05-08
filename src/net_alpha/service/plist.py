"""Render the launchd plist (XML, plistlib-formatted)."""

from __future__ import annotations

import plistlib

from net_alpha.service.paths import PLIST_LABEL


def render(*, wrapper_path: str, log_path: str) -> bytes:
    body = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [wrapper_path],
        "RunAtLoad": True,
        "KeepAlive": {"Crashed": True, "SuccessfulExit": False},
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
        "ProcessType": "Background",
        "SoftResourceLimits": {
            "NumberOfFiles": 512,
            "ResidentSetSize": 268_435_456,  # 256 MB
        },
    }
    return plistlib.dumps(body, fmt=plistlib.FMT_XML)

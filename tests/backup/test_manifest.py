from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from net_alpha.backup.manifest import MANIFEST_FORMAT_VERSION, Manifest


def test_manifest_roundtrip_json():
    m = Manifest(
        format_version=MANIFEST_FORMAT_VERSION,
        app_version="0.57.0",
        schema_version=20,
        created_at=datetime(2026, 5, 10, 15, 30, 0, tzinfo=UTC),
        reason="manual",
        hostname="test-host",
        db_sha256="a" * 64,
        db_size_bytes=1024,
        row_counts={"trades": 42, "lots": 30},
        account_labels=["schwab/taxable"],
        encrypted=False,
    )
    blob = m.to_json_bytes()
    loaded = Manifest.from_json_bytes(blob)
    assert loaded == m


def test_manifest_ignores_unknown_fields():
    data = {
        "format_version": MANIFEST_FORMAT_VERSION,
        "app_version": "0.99.0",
        "schema_version": 99,
        "created_at": "2026-05-10T15:30:00+00:00",
        "reason": "daily",
        "hostname": "h",
        "db_sha256": "b" * 64,
        "db_size_bytes": 1,
        "row_counts": {},
        "account_labels": [],
        "encrypted": False,
        "future_field_we_added_later": "ignore me",
    }
    loaded = Manifest.from_json_bytes(json.dumps(data).encode())
    assert loaded.app_version == "0.99.0"


def test_manifest_rejects_missing_required():
    with pytest.raises(ValueError):
        Manifest.from_json_bytes(b'{"format_version": 1}')

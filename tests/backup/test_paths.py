from __future__ import annotations

from datetime import UTC, datetime

from net_alpha.backup import paths


def test_backups_dir_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.backups_dir() == tmp_path / ".net_alpha" / "backups"


def test_bundle_filename_unencrypted():
    ts = datetime(2026, 5, 10, 15, 30, 45, tzinfo=UTC)
    name = paths.bundle_filename(created_at=ts, reason="manual", encrypted=False)
    assert name == "wash-alpha-20260510-153045-manual.tar.gz"


def test_bundle_filename_encrypted():
    ts = datetime(2026, 5, 10, 15, 30, 45, tzinfo=UTC)
    name = paths.bundle_filename(created_at=ts, reason="pre-import", encrypted=True)
    assert name == "wash-alpha-20260510-153045-pre-import.tar.gz.enc"


def test_sanitize_reason_strips_unsafe():
    assert paths.sanitize_reason("pre-import") == "pre-import"
    assert paths.sanitize_reason("My Reason!") == "my-reason"
    assert paths.sanitize_reason("") == "manual"

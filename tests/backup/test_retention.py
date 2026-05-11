from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from net_alpha.backup.retention import BackupFile, RetentionPolicy, select_for_deletion


def _bf(name: str, reason: str, days_ago: int, size: int = 1024) -> BackupFile:
    return BackupFile(
        path=Path(f"/tmp/{name}"),
        reason=reason,
        created_at=datetime(2026, 5, 10, tzinfo=UTC) - timedelta(days=days_ago),
        size_bytes=size,
    )


_NOW = datetime(2026, 5, 10, tzinfo=UTC)
_POLICY = RetentionPolicy(daily_keep=14, pre_keep=10, size_cap_bytes=2 * 1024**3)


def test_manual_is_never_deleted():
    bundles = [_bf(f"m{i}", "manual", i) for i in range(50)]
    assert select_for_deletion(bundles, policy=_POLICY, now=_NOW) == []


def test_daily_keeps_newest_n():
    bundles = [_bf(f"d{i}", "daily", i) for i in range(20)]
    deleted = select_for_deletion(bundles, policy=_POLICY, now=_NOW)
    assert {b.path.name for b in deleted} == {f"d{i}" for i in range(14, 20)}


def test_pre_keeps_newest_n_across_reasons():
    bundles = [_bf(f"p{i}", "pre-import", i) for i in range(7)] + [
        _bf(f"q{i}", "pre-imports-rm", i + 7) for i in range(8)
    ]
    deleted = select_for_deletion(bundles, policy=_POLICY, now=_NOW)
    # 15 total pre-*, keep newest 10, delete 5 oldest
    assert len(deleted) == 5
    # The 5 deleted are the oldest by created_at
    oldest = sorted(bundles, key=lambda b: b.created_at)[:5]
    assert set(deleted) == set(oldest)


def test_size_cap_prunes_non_manual():
    big = 500 * 1024**2  # 500 MB each
    bundles = [
        _bf("manual1", "manual", 0, big),
        _bf("daily1", "daily", 1, big),
        _bf("daily2", "daily", 2, big),
        _bf("daily3", "daily", 3, big),
        _bf("daily4", "daily", 4, big),
        _bf("daily5", "daily", 5, big),
    ]
    # Total = 3 GB > 2 GB cap. Manual is sacred, so daily oldest get pruned.
    deleted = select_for_deletion(bundles, policy=_POLICY, now=_NOW)
    names = {b.path.name for b in deleted}
    assert "manual1" not in names
    assert "daily5" in names  # oldest goes first
    # Need to drop 1 GB worth (= 2 dailies) to get under 2 GB.
    assert len(deleted) == 2
    assert names == {"daily5", "daily4"}


def test_manual_only_exceeds_cap_logs_no_prune(caplog):
    big = 1500 * 1024**2  # 1.5 GB each
    bundles = [_bf("m1", "manual", 0, big), _bf("m2", "manual", 1, big)]
    deleted = select_for_deletion(bundles, policy=_POLICY, now=_NOW)
    assert deleted == []
    assert any("manual" in r.message.lower() for r in caplog.records)


def test_empty_input():
    assert select_for_deletion([], policy=_POLICY, now=_NOW) == []

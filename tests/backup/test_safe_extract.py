"""Path-traversal-safe tarball extraction.

The previous bundle.py fallback for old Python (lacking the `filter="data"`
keyword) called the unfiltered ``tf.extractall(out_dir)``, re-introducing the
CVE-2007-4559 path-traversal that the filter was added to prevent. The
``_safe_extract`` helper validates each member before writing.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from net_alpha.backup.bundle import _safe_extract


def _build_tarball(members: list[tuple[str, bytes]]) -> bytes:
    """Build an in-memory tar.gz with the named members + payloads."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _open(raw: bytes) -> tarfile.TarFile:
    return tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")


def test_extracts_normal_members(tmp_path: Path) -> None:
    raw = _build_tarball([("db/net_alpha.db", b"fakedb"), ("manifest.json", b"{}")])
    with _open(raw) as tf:
        _safe_extract(tf, tmp_path)
    assert (tmp_path / "db" / "net_alpha.db").read_bytes() == b"fakedb"
    assert (tmp_path / "manifest.json").read_bytes() == b"{}"


def test_rejects_absolute_path_member(tmp_path: Path) -> None:
    raw = _build_tarball([("/etc/evil.txt", b"pwned")])
    with _open(raw) as tf, pytest.raises(ValueError, match="unsafe path"):
        _safe_extract(tf, tmp_path)
    # And nothing landed at /etc/evil.txt (would be a system write).
    assert not Path("/etc/evil.txt").exists()


def test_rejects_dotdot_traversal_member(tmp_path: Path) -> None:
    raw = _build_tarball([("../escape.txt", b"pwned")])
    with _open(raw) as tf, pytest.raises(ValueError, match="unsafe path"):
        _safe_extract(tf, tmp_path)
    assert not (tmp_path.parent / "escape.txt").exists()


def test_rejects_nested_dotdot_traversal_member(tmp_path: Path) -> None:
    raw = _build_tarball([("foo/../../escape.txt", b"pwned")])
    with _open(raw) as tf, pytest.raises(ValueError, match="unsafe path"):
        _safe_extract(tf, tmp_path)
    assert not (tmp_path.parent.parent / "escape.txt").exists()


def test_rejects_symlink_member(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="evil_symlink")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)
    raw = buf.getvalue()
    with _open(raw) as tf, pytest.raises(ValueError, match="link target"):
        _safe_extract(tf, tmp_path)
    assert not (tmp_path / "evil_symlink").exists()


def test_rejects_hardlink_member(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="evil_hardlink")
        info.type = tarfile.LNKTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)
    raw = buf.getvalue()
    with _open(raw) as tf, pytest.raises(ValueError, match="link target"):
        _safe_extract(tf, tmp_path)

import os

import pytest

from net_alpha.service import lock, paths


def test_acquire_writes_current_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    lock.acquire()
    assert paths.pid_file().read_text().strip() == str(os.getpid())


def test_acquire_raises_if_live_pid_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.pid_file().write_text(str(os.getpid()))
    with pytest.raises(lock.AlreadyRunning):
        lock.acquire()


def test_acquire_breaks_stale_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.pid_file().write_text("999999")  # almost certainly not a real pid
    lock.acquire()  # should overwrite
    assert paths.pid_file().read_text().strip() == str(os.getpid())


def test_release_removes_pid_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    lock.acquire()
    lock.release()
    assert not paths.pid_file().exists()


def test_pid_alive_returns_true_for_self():
    assert lock._pid_alive(os.getpid()) is True


def test_pid_alive_returns_false_for_huge_unused():
    assert lock._pid_alive(999999) is False

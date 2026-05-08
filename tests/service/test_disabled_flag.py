from net_alpha.service import disabled_flag, paths


def test_set_writes_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    disabled_flag.set("user requested stop")
    assert paths.disabled_flag().exists()
    assert "user requested stop" in paths.disabled_flag().read_text()


def test_is_set_returns_true_when_present(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    disabled_flag.set("x")
    assert disabled_flag.is_set() is True


def test_is_set_returns_false_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    assert disabled_flag.is_set() is False


def test_clear_removes_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    disabled_flag.set("x")
    disabled_flag.clear()
    assert disabled_flag.is_set() is False


def test_clear_when_absent_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    disabled_flag.clear()  # must not raise


def test_set_includes_iso_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    disabled_flag.set("manual")
    contents = paths.disabled_flag().read_text()
    # ISO 8601 date prefix
    assert contents.split("T")[0].count("-") == 2

from net_alpha.service import paths


def test_run_dir_is_under_net_alpha_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.run_dir() == tmp_path / ".net_alpha" / "run"


def test_pid_file_path():
    assert paths.pid_file().name == "service.pid"
    assert paths.pid_file().parent == paths.run_dir()


def test_disabled_flag_path():
    assert paths.disabled_flag().name == "disabled"
    assert paths.disabled_flag().parent == paths.run_dir()


def test_plist_path_under_launchagents(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.plist_file() == tmp_path / "Library" / "LaunchAgents" / "com.netalpha.service.plist"


def test_wrapper_path_under_net_alpha_bin(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.wrapper_script() == tmp_path / ".net_alpha" / "bin" / "net-alpha-wrap"


def test_sandbox_profile_path():
    assert paths.sandbox_profile().name == "sandbox.sb"
    assert paths.sandbox_profile().parent == paths.run_dir()


def test_log_file_path():
    assert paths.log_file().name == "service.log"


def test_ensure_dirs_creates_required_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths.ensure_dirs()
    assert (tmp_path / ".net_alpha" / "run").is_dir()
    assert (tmp_path / ".net_alpha" / "bin").is_dir()
    assert (tmp_path / ".net_alpha" / "logs").is_dir()
    assert (tmp_path / "Library" / "LaunchAgents").is_dir()

from net_alpha.verify.tolerances import (
    Severity,
    Tolerance,
    classify,
    load_tolerances,
)


def test_classify_within_tolerance_is_ok():
    tol = Tolerance(abs=0.01, rel=0.0001)
    assert classify(ours=100.005, theirs=100.0, tol=tol) == Severity.OK


def test_classify_outside_tolerance_within_10x_is_warn():
    tol = Tolerance(abs=0.01, rel=0.0001)
    # delta = 0.05 > 0.01 (abs), <= 0.1 (10×abs)
    assert classify(ours=100.05, theirs=100.0, tol=tol) == Severity.WARN


def test_classify_beyond_10x_is_fail():
    tol = Tolerance(abs=0.01, rel=0.0001)
    assert classify(ours=100.50, theirs=100.0, tol=tol) == Severity.FAIL


def test_classify_uses_relative_when_larger_than_abs():
    tol = Tolerance(abs=0.01, rel=0.01)  # 1% relative
    # 1% of 1000 = 10.0, well above 0.01 abs
    assert classify(ours=1005.0, theirs=1000.0, tol=tol) == Severity.OK  # 5 < 10
    assert classify(ours=1015.0, theirs=1000.0, tol=tol) == Severity.WARN  # 15 > 10, ≤ 100


def test_load_tolerances_returns_defaults_when_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    cfg = load_tolerances()
    assert cfg.invariants.abs == 0.01
    assert cfg.realized.abs == 0.50
    assert cfg.positions_qty.abs == 0.0
    assert cfg.positions_basis.abs == 1.00
    assert cfg.positions_mv.abs == 5.00


def test_load_tolerances_applies_user_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("verify:\n  tolerances:\n    realized_abs: 1.00\n    positions_mv_rel: 0.01\n")
    cfg = load_tolerances()
    assert cfg.realized.abs == 1.00  # overridden
    assert cfg.realized.rel == 0.001  # default preserved
    assert cfg.positions_mv.rel == 0.01  # overridden

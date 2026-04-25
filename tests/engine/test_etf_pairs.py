import os
import tempfile
from pathlib import Path

from net_alpha.engine.etf_pairs import load_etf_pairs


def test_load_bundled_pairs():
    pairs = load_etf_pairs(user_path=None)
    assert "SPY" in pairs["sp500"]
    assert "VOO" in pairs["sp500"]
    assert "QQQ" in pairs["nasdaq100"]
    assert "GLD" in pairs["gold"]


def test_user_pairs_extend_defaults():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("tech_growth:\n  - VGT\n  - XLK\n")
        f.flush()
        try:
            pairs = load_etf_pairs(user_path=Path(f.name))
            # Bundled pairs still present
            assert "SPY" in pairs["sp500"]
            # User pairs added
            assert "VGT" in pairs["tech_growth"]
            assert "XLK" in pairs["tech_growth"]
        finally:
            os.unlink(f.name)


def test_user_pairs_do_not_replace_defaults():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("sp500:\n  - VFINX\n")
        f.flush()
        try:
            pairs = load_etf_pairs(user_path=Path(f.name))
            # Bundled entries preserved
            assert "SPY" in pairs["sp500"]
            assert "VOO" in pairs["sp500"]
            # User entry merged in
            assert "VFINX" in pairs["sp500"]
        finally:
            os.unlink(f.name)


def test_missing_user_file_ignored():
    pairs = load_etf_pairs(user_path=Path("/nonexistent/path.yaml"))
    assert "SPY" in pairs["sp500"]

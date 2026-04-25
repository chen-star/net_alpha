from net_alpha.engine.etf_pairs import load_etf_pairs


def test_load_etf_pairs_returns_known_groups():
    pairs = load_etf_pairs()
    flat = {t for group in pairs.values() for t in group}
    assert "SPY" in flat
    assert "VOO" in flat


def test_user_override_extends_bundled_pairs(tmp_path):
    user_yaml = tmp_path / "etf_pairs.yaml"
    user_yaml.write_text("custom_pair:\n  - FOO\n  - BAR\n")
    pairs = load_etf_pairs(user_path=str(user_yaml))
    flat = {t for group in pairs.values() for t in group}
    # User pairs added
    assert "FOO" in flat
    assert "BAR" in flat
    # Bundled pairs still present
    assert "SPY" in flat

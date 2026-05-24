from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "net_alpha" / "web" / "static"
APP_SRC_CSS = SRC / "app.src.css"
APP_CSS = SRC / "app.css"


def test_premium_tokens_present_in_source():
    src = APP_SRC_CSS.read_text()
    expected = [
        "--shadow-feature:",
        "--gradient-edge-top:",
        "--ambiance-wash:",
        "--ease-spring:",
    ]
    missing = [t for t in expected if t not in src]
    assert not missing, f"Missing tokens in app.src.css: {missing}"


def test_premium_tokens_defined_for_light_theme():
    """Per-theme tokens must exist in the light block too (dark is primary,
    but light parity is required)."""
    src = APP_SRC_CSS.read_text()
    light_start = src.index('[data-theme="light"]')
    light_block = src[light_start:]
    for tok in ["--shadow-feature:", "--gradient-edge-top:", "--ambiance-wash:"]:
        assert tok in light_block, f"{tok} missing from light theme block"

from pathlib import Path

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app

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


def test_panel_feature_class_defined():
    src = APP_SRC_CSS.read_text()
    assert ".panel-feature" in src


def test_kpi_hero_mesh_uses_two_radials():
    """The hero ::before should layer two radial gradients (signature + cyan)
    rather than the single radial it shipped with."""
    src = APP_SRC_CSS.read_text()
    hero_idx = src.index(".kpi-hero::before")
    block = src[hero_idx : hero_idx + 600]
    assert block.count("radial-gradient") >= 2, "hero mesh should layer 2+ radials"


def test_body_ambiance_class_defined():
    src = APP_SRC_CSS.read_text()
    assert ".na-ambiance" in src
    assert "var(--ambiance-wash)" in src


def test_reveal_animation_gated_on_no_preference():
    """Entrance reveal must live inside prefers-reduced-motion: no-preference
    so reduced-motion users never hit a transient opacity:0 state."""
    src = APP_SRC_CSS.read_text()
    assert "@keyframes na-reveal" in src
    assert ".js-reveal" in src
    npref_idx = src.index("(prefers-reduced-motion: no-preference)")
    # The .js-reveal animation assignment must appear after the no-preference guard.
    assert src.index(".js-reveal >", npref_idx) > npref_idx


def test_swap_crossfade_rules_present():
    src = APP_SRC_CSS.read_text()
    assert ".htmx-swapping" in src
    assert ".htmx-settling" in src


def _client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def test_countup_js_served(tmp_path):
    resp = _client(tmp_path).get("/static/countup.js")
    assert resp.status_code == 200
    assert "js-countup-num" in resp.text
    assert "prefers-reduced-motion" in resp.text


def test_base_registers_countup(tmp_path):
    resp = _client(tmp_path).get("/")
    assert resp.status_code == 200
    assert "/static/countup.js" in resp.text
    assert "na-ambiance" in resp.text  # body ambiance class wired in Step 4


def test_kpis_fragment_has_countup_spans(tmp_path):
    # Seed one import so the "with data" KPI path renders numbers.
    from sqlalchemy import text

    from net_alpha.db.connection import get_engine

    settings = Settings(data_dir=tmp_path)
    # create_app initialises the schema; build client first so the DB exists.
    client = TestClient(create_app(settings))
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )
    resp = client.get("/portfolio/kpis?period=ytd")
    assert resp.status_code == 200
    assert "js-countup-num" in resp.text


def test_overview_has_feature_panel_and_reveal(tmp_path):
    from sqlalchemy import text

    from net_alpha.db.connection import get_engine

    settings = Settings(data_dir=tmp_path)
    # create_app initialises the schema; build client first so the DB exists.
    client = TestClient(create_app(settings))
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )
    # _portfolio_body.html is served as an HTMX fragment, not inline on /.
    resp = client.get("/portfolio/body?period=ytd")
    assert resp.status_code == 200
    assert "js-reveal" in resp.text
    assert "--reveal-i:" in resp.text
    assert "panel-feature" in resp.text

from datetime import date

from net_alpha.audit.provenance import Period, RealizedPLRef, encode_metric_ref
from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_macro_emits_correct_hx_get(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    env = app.state.templates.env
    template = env.from_string('{% from "_provenance_macros.html" import provenance_link %}{{ provenance_link(ref) }}')
    ref = RealizedPLRef(
        kind="realized_pl",
        period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1), label="YTD 2026"),
        account_id=1,
        symbol=None,
    )
    rendered = template.render(ref=ref)
    expected_path = f"/provenance/{encode_metric_ref(ref)}"
    assert f'hx-get="{expected_path}"' in rendered
    assert "provenance-trigger" in rendered

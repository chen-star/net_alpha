"""KpiSet no longer carries the unused today_change / today_pct fields.

The Today tile that used to consume them was orphaned — no template renders
it (monthly CSV-import workflow has no use for an intraday delta). The
compute path is gone with it.
"""

from dataclasses import fields

from net_alpha.portfolio.models import KpiSet


def test_kpiset_has_no_today_fields():
    names = {f.name for f in fields(KpiSet)}
    assert "today_change" not in names
    assert "today_pct" not in names

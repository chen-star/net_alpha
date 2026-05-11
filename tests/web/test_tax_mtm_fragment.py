"""/tax?view=performance — §1256 year-end MTM table fragment."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Section1256MTM


def _seed_import(builders, repo) -> None:
    """Seed a minimal import so has_any_tax_data is truthy."""
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "SPY", date(2025, 1, 3))],
    )


def test_tax_performance_renders_mtm_section(client, repo, builders):
    """MTM rows seeded in the DB appear in the performance view."""
    _seed_import(builders, repo)
    repo.save_section_1256_mtm(
        [
            Section1256MTM(
                position_key="SPX|4000.0|2026-06-19|C|fidelity",
                tax_year=2025,
                last_business_day=date(2025, 12, 31),
                fmv=Decimal("150"),
                basis_before=Decimal("100"),
                unrealized_pnl=Decimal("50.00"),
                long_term_portion=Decimal("30.00"),
                short_term_portion=Decimal("20.00"),
                fmv_source="yahoo_close",
                ticker="SPX",
                account="fidelity",
            )
        ]
    )
    resp = client.get("/tax?view=performance&year=2025")
    assert resp.status_code == 200
    body = resp.text
    assert "§1256 Year-End Mark-to-Market" in body
    assert "SPX" in body
    assert "50.00" in body  # the unrealized P&L cell


def test_tax_performance_handles_empty_mtm(client, repo, builders):
    """No MTM rows → page renders cleanly without the MTM section."""
    _seed_import(builders, repo)
    resp = client.get("/tax?view=performance&year=2025")
    assert resp.status_code == 200
    assert "section-1256-mtm" not in resp.text


def test_tax_performance_renders_black_scholes_badge(client, repo, builders):
    """A Black-Scholes-sourced MTM row should render with the warning-color badge."""
    _seed_import(builders, repo)
    repo.save_section_1256_mtm(
        [
            Section1256MTM(
                position_key="SPX|4000.0|2026-06-19|C|personal",
                tax_year=2025,
                last_business_day=date(2025, 12, 31),
                fmv=Decimal("125.50"),
                basis_before=Decimal("100.00"),
                unrealized_pnl=Decimal("25.50"),
                long_term_portion=Decimal("15.30"),
                short_term_portion=Decimal("10.20"),
                fmv_source="black_scholes",
                ticker="SPX",
                account="personal",
            )
        ]
    )
    resp = client.get("/tax?view=performance&year=2025")
    assert resp.status_code == 200
    assert "Black-Scholes" in resp.text

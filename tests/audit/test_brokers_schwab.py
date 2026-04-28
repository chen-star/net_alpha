from __future__ import annotations

from datetime import date

from net_alpha.audit.brokers.schwab import SchwabGLProvider
from net_alpha.models.realized_gl import RealizedGLLot


def test_schwab_provider_translates_gl_lots(repo, schwab_account):
    repo.add_gl_lots(
        schwab_account,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display="Schwab/Tax",
                symbol_raw="AAPL",
                ticker="AAPL",
                closed_date=date(2026, 4, 1),
                opened_date=date(2026, 1, 1),
                quantity=10.0,
                proceeds=1500.0,
                cost_basis=1000.0,
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Long Term",
            )
        ],
    )
    provider = SchwabGLProvider(repo)
    assert provider.supports(schwab_account.id) is True

    lots = provider.get_lot_detail(schwab_account.id, "AAPL")
    assert len(lots) == 1
    bl = lots[0]
    assert bl.symbol == "AAPL"
    assert bl.account_id == schwab_account.id
    assert bl.cost_basis == 1000.0
    assert bl.proceeds == 1500.0
    assert bl.source_label.startswith("Schwab")


def test_schwab_provider_supports_only_schwab(repo):
    other = repo.get_or_create_account(broker="Fidelity", label="Roth")
    provider = SchwabGLProvider(repo)
    assert provider.supports(other.id) is False

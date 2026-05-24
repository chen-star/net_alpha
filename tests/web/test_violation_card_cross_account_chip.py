"""audit #32 — `_violation_card.html` rendered the cross-account source tag
with `.chip-probable` (yellow), colliding with the wash-sale confidence
palette reserved by CLAUDE.md for Confirmed/Probable/Unclear. The neutral
`.chip-source` class now carries the source decoration.

The card is included from the ticker page (`ticker.html`), so we seed a
WashSaleViolation whose loss leg sits in one account and replacement leg in
another, then assert the rendered ticker page shows the cross-account tag
as `chip-source`, not `chip-probable`.
"""

from __future__ import annotations

from datetime import date

from net_alpha.models.domain import WashSaleViolation

_YR = date.today().year


def test_cross_account_chip_uses_chip_source_not_chip_probable(client, repo):
    repo.get_or_create_account("schwab", "personal")
    repo.get_or_create_account("schwab", "roth")
    vs = [
        WashSaleViolation(
            loss_trade_id="1",
            replacement_trade_id="2",
            confidence="Confirmed",
            disallowed_loss=200.0,
            matched_quantity=10.0,
            ticker="TSLA",
            loss_account="schwab/personal",
            buy_account="schwab/roth",
            loss_sale_date=date(_YR, 6, 1),
            triggering_buy_date=date(_YR, 6, 12),
            source="engine",
        )
    ]
    repo.replace_violations_in_window(date(_YR, 1, 1), date(_YR, 12, 31), vs)

    resp = client.get("/ticker/TSLA")
    assert resp.status_code == 200
    body = resp.text

    # The Cross-account span lives inside `_violation_card.html`.
    assert ">Cross-account<" in body
    # Find the span carrying the "Cross-account" label.
    snippet = body.split(">Cross-account<")[0]
    # The most recent `<span` tag opening before ">Cross-account<" is the
    # one whose classes we care about.
    open_tag = snippet.rsplit("<span", 1)[-1]
    assert "chip-source" in open_tag, f"Cross-account span must use chip-source, got: <span{open_tag}"
    assert "chip-probable" not in open_tag, (
        f"Cross-account span must not borrow the confidence palette (chip-probable): <span{open_tag}"
    )

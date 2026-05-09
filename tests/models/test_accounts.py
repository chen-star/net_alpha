from net_alpha.models.accounts import Account, AccountType


def test_account_type_enum_values():
    assert AccountType.TAXABLE.value == "taxable"
    assert AccountType.TRAD_IRA.value == "trad_ira"
    assert AccountType.ROTH_IRA.value == "roth_ira"
    assert AccountType.K401.value == "401k"
    assert AccountType.HSA.value == "hsa"
    assert AccountType.OTHER.value == "other"


def test_is_tax_advantaged():
    assert AccountType.TAXABLE.is_tax_advantaged is False
    for t in [AccountType.TRAD_IRA, AccountType.ROTH_IRA, AccountType.K401, AccountType.HSA]:
        assert t.is_tax_advantaged is True
    assert AccountType.OTHER.is_tax_advantaged is False


def test_account_round_trip():
    a = Account(broker="schwab", label="personal", type=AccountType.TAXABLE)
    assert a.broker == "schwab"
    assert a.label == "personal"
    assert a.type == AccountType.TAXABLE


def test_account_default_type_taxable():
    a = Account(broker="schwab", label="personal")
    assert a.type == AccountType.TAXABLE

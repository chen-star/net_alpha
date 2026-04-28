from net_alpha.audit.brokers.registry import get_provider_for_account
from net_alpha.audit.brokers.schwab import SchwabGLProvider


def test_returns_schwab_provider_for_schwab_account(repo, schwab_account):
    provider = get_provider_for_account(schwab_account.id, repo)
    assert isinstance(provider, SchwabGLProvider)


def test_returns_none_for_unsupported_broker(repo):
    fid = repo.get_or_create_account(broker="Fidelity", label="Roth")
    provider = get_provider_for_account(fid.id, repo)
    assert provider is None

from net_alpha.audit.hygiene import collect_issues


def test_empty_repo_returns_no_issues(repo):
    issues = collect_issues(repo)
    assert issues == []

from pathlib import Path

from net_alpha.audit.hygiene import HygieneIssue, collect_issues
from net_alpha.config import Settings


def test_collect_issues_includes_tax_config_missing(tmp_path: Path, repo) -> None:
    settings = Settings(data_dir=tmp_path)
    # No config.yaml at all -> tax_config_missing surfaces as info.
    issues = collect_issues(repo, settings=settings)
    matching = [i for i in issues if i.category == "tax_config_missing"]
    assert len(matching) == 1
    issue: HygieneIssue = matching[0]
    assert issue.severity == "info"
    assert "tax bracket" in issue.summary.lower()


def test_collect_issues_omits_tax_config_missing_when_present(tmp_path: Path, repo) -> None:
    settings = Settings(data_dir=tmp_path)
    (tmp_path / "config.yaml").write_text("tax:\n  filing_status: single\n  federal_marginal_rate: 0.22\n")
    issues = collect_issues(repo, settings=settings)
    assert all(i.category != "tax_config_missing" for i in issues)


def test_collect_issues_works_without_settings_kwarg(repo) -> None:
    # Backwards-compatible: callers that don't pass settings still work.
    issues = collect_issues(repo)
    # No settings -> we cannot determine config presence; we omit the row entirely.
    assert all(i.category != "tax_config_missing" for i in issues)

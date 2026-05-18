"""Multi-file upload must support per-file account labels.

Regression for the I1 bug: the upload route accepted a single
``account: str`` form field and applied it to every uploaded file. A
user dropping ``schwab_joint.csv`` and ``schwab_ira.csv`` together had
both files collapsed into one account, which silently broke cross-
account wash-sale detection AND the Rev. Rul. 2008-5 IRA-trap
classifier (which needs the IRA leg to be in a distinct account from
the taxable leg).

The fix is to accept ``account`` as a repeated form field aligned 1:1
with the ``files`` list. A length mismatch is rejected with HTTP 400.
"""

from __future__ import annotations

from pathlib import Path

TX_FIXTURE = Path(__file__).parent / "fixtures" / "schwab_minimal.csv"


def test_upload_two_files_two_account_labels_creates_two_accounts(client, repo):
    """Two CSVs + two account labels → two distinct accounts, each with its file's trades."""
    with TX_FIXTURE.open("rb") as a, TX_FIXTURE.open("rb") as b:
        resp = client.post(
            "/imports",
            files=[
                ("files", ("joint.csv", a, "text/csv")),
                ("files", ("ira.csv", b, "text/csv")),
            ],
            data={"account": ["joint", "ira"]},
            follow_redirects=False,
        )
    assert resp.status_code == 303

    joint = repo.get_account("schwab", "joint")
    ira = repo.get_account("schwab", "ira")
    assert joint is not None
    assert ira is not None
    assert joint.id != ira.id

    # Each account should own its own trade rows.
    joint_trades = [t for t in repo.all_trades() if t.account == joint.display()]
    ira_trades = [t for t in repo.all_trades() if t.account == ira.display()]
    assert len(joint_trades) > 0
    assert len(ira_trades) > 0


def test_upload_single_file_single_account_still_works(client, repo):
    """The single-file case (legacy form) must remain functional."""
    with TX_FIXTURE.open("rb") as f:
        resp = client.post(
            "/imports",
            files=[("files", ("schwab.csv", f, "text/csv"))],
            data={"account": "personal"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    acct = repo.get_account("schwab", "personal")
    assert acct is not None


def test_upload_one_label_broadcasts_to_all_files(client, repo):
    """1 label + 2 files → single account (legacy behavior preserved).

    This is the "transactions + Realized G/L for the same account"
    workflow where two files genuinely belong to one account.
    """
    with TX_FIXTURE.open("rb") as a, TX_FIXTURE.open("rb") as b:
        resp = client.post(
            "/imports",
            files=[
                ("files", ("a.csv", a, "text/csv")),
                ("files", ("b.csv", b, "text/csv")),
            ],
            data={"account": "shared"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    # Both files land in the same account.
    shared = repo.get_account("schwab", "shared")
    assert shared is not None


def test_upload_account_count_mismatch_rejected(client):
    """Account-count must match file-count (or be a single label).
    3 labels + 2 files → 400.
    """
    with TX_FIXTURE.open("rb") as a, TX_FIXTURE.open("rb") as b:
        resp = client.post(
            "/imports",
            files=[
                ("files", ("a.csv", a, "text/csv")),
                ("files", ("b.csv", b, "text/csv")),
            ],
            data={"account": ["x", "y", "z"]},
            follow_redirects=False,
        )
    assert resp.status_code == 400


def test_upload_empty_account_label_rejected(client):
    """An empty per-file label is rejected — every file must declare its
    account explicitly."""
    with TX_FIXTURE.open("rb") as a, TX_FIXTURE.open("rb") as b:
        resp = client.post(
            "/imports",
            files=[
                ("files", ("a.csv", a, "text/csv")),
                ("files", ("b.csv", b, "text/csv")),
            ],
            data={"account": ["x", ""]},
            follow_redirects=False,
        )
    assert resp.status_code == 400


def test_upload_per_file_distinct_taxable_and_roth(client, repo):
    """Per-file labels let IRA-trap detection work: the loss-side trade
    in one account + the rebuy in a Roth account must result in two
    accounts so the engine can classify the wash as ``permanent_ira``.
    """
    with TX_FIXTURE.open("rb") as a, TX_FIXTURE.open("rb") as b:
        resp = client.post(
            "/imports",
            files=[
                ("files", ("taxable.csv", a, "text/csv")),
                ("files", ("roth.csv", b, "text/csv")),
            ],
            data={"account": ["taxable", "roth"]},
            follow_redirects=False,
        )
    assert resp.status_code == 303

    taxable = repo.get_account("schwab", "taxable")
    roth = repo.get_account("schwab", "roth")
    assert taxable is not None and roth is not None
    assert taxable.id != roth.id

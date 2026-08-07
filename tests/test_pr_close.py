"""Atomic pr_close dry-run."""

from lokay.proc import pr_close


def test_pr_close_dry_run(monkeypatch):
    # No network: mutations_allowed false without --live.
    code = pr_close.main(
        ["--repo", "mikolaj92/lokay", "--pr", "4", "--comment", "test"]
    )
    assert code == 0

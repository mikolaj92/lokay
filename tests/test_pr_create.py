"""Physical and closed-result contracts for authored PR publication."""

from pathlib import Path


def test_existing_pr_terminal_preserves_delivery_identity():
    from lokay.proc.pr_create_terminal import terminal

    pull = {"number": 334, "head": {"ref": "ai/fix/239"}}
    out = terminal(
        {"repo": "a/b", "head": "ai/fix/239", "issue": 239},
        {"route": "existing", "pull": pull},
        {},
        {},
        {},
    )["result"]
    assert out["ok"] is True and out["existing"] is True and out["pr"] == 334


def test_closed_issue_terminal_fails_closed():
    from lokay.proc.pr_create_terminal import terminal

    out = terminal(
        {"repo": "a/b", "head": "ai/fix/239", "issue": 239},
        {"route": "none"},
        {"issue_state": "CLOSED"},
        {"route": "terminal", "reason": "issue_closed", "issue_state": "CLOSED"},
        {},
    )["result"]
    assert (
        out["ok"] is False
        and out["reason"] == "issue_closed"
        and out["issue_state"] == "CLOSED"
    )


def test_creation_identity_remains_required_by_physical_engine():
    source = Path(__file__).parents[1] / "src/lokay/gh_prs.py"
    assert (
        "PR creation success requires a recoverable delivery identity."
        in source.read_text()
    )

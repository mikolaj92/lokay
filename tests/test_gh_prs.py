"""find_pr_fixing_issue on this mill paginates only mikolaj92/lokay."""

from __future__ import annotations

import pytest

import json

from lokay.gh_prs import find_pr_fixing_issue
from lokay.runner import CommandResult, CommandSpec


class _Runner:
    def __init__(self, rows: object) -> None:
        self.rows = rows
        self.calls: list[tuple[str, ...]] = []

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=0,
            stdout=json.dumps(self.rows),
        )


def _closing_row(issue: int) -> dict:
    return {
        "number": 99,
        "body": f"Fixes #{issue}",
        "state": "OPEN",
        "merged_at": None,
    }


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_find_pr_fixing_issue_temida_returns_none_without_gh() -> None:
    runner = _Runner([_closing_row(436)])
    assert find_pr_fixing_issue(runner, "mikolaj92/Temida", 436, live=True) is None
    assert runner.calls == []


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_find_pr_fixing_issue_reviewkit_returns_none_without_gh() -> None:
    runner = _Runner([_closing_row(436)])
    assert find_pr_fixing_issue(runner, "mikolaj92/reviewkit", 436, live=True) is None
    assert runner.calls == []


def test_find_pr_fixing_issue_rejects_mixed_slurped_pages() -> None:
    runner = _Runner([{}, [_closing_row(436)]])
    try:
        find_pr_fixing_issue(runner, "mikolaj92/lokay", 436, live=True)
    except ValueError as exc:
        assert "cannot mix rows and pages" in str(exc)
    else:
        raise AssertionError("mixed pagination shape must fail closed")


def test_find_pr_fixing_issue_flattens_all_slurped_pages() -> None:
    row = _closing_row(436)
    runner = _Runner([[], [row]])
    assert find_pr_fixing_issue(runner, "mikolaj92/lokay", 436, live=True) == row


def test_find_pr_fixing_issue_lokay_still_paginates() -> None:
    row = _closing_row(436)
    runner = _Runner([row])
    got = find_pr_fixing_issue(runner, "mikolaj92/lokay", 436, live=True)
    assert got == row
    assert runner.calls, "lokay must still call gh"
    argv = runner.calls[0]
    assert argv[0] == "gh"
    assert "repos/mikolaj92/lokay/pulls" in argv
    assert "--paginate" in argv


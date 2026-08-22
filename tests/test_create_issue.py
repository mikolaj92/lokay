"""Issue creation returns only its own recoverable delivery identity."""

from __future__ import annotations

import pytest

from lokay.gh_issues import create_issue
from lokay.runner import CommandResult


class _Runner:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.calls: list[tuple[str, ...]] = []

    def run_checked(self, spec, *, live):
        self.calls.append(spec.argv)
        return CommandResult(
            spec=spec, executed=live, returncode=0, stdout=self.stdout
        )

    def run(self, spec, *, live):
        raise AssertionError("same-title list fallback must not run")


def test_create_issue_requires_number_in_its_own_url() -> None:
    runner = _Runner("created successfully\n")
    with pytest.raises(RuntimeError, match="succeeded but number unknown"):
        create_issue(
            runner,
            repo="mikolaj92/lokay",
            title="same title",
            body="body",
            live=True,
        )
    assert len(runner.calls) == 1


def test_create_issue_returns_number_from_its_own_url() -> None:
    runner = _Runner("https://github.com/mikolaj92/lokay/issues/721\n")
    assert create_issue(
        runner,
        repo="mikolaj92/lokay",
        title="child",
        body="body",
        live=True,
    ) == {
        "number": 721,
        "url": "https://github.com/mikolaj92/lokay/issues/721",
        "title": "child",
        "repo": "mikolaj92/lokay",
    }

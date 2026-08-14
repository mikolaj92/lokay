"""ensure_labels creates missing labels before add-label."""

from __future__ import annotations

import pytest

from lokay.gh_issues import add_issue_labels, ensure_labels, remove_issue_labels
from lokay.runner import CommandResult, CommandSpec


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        # first create fails as already exists for ai:blocked; succeeds for ai:ready
        if "label" in spec.argv and "create" in spec.argv:
            name = spec.argv[2]
            if name == "ai:blocked":
                return CommandResult(
                    spec=spec,
                    executed=live,
                    returncode=1,
                    stderr="label already exists",
                )
            return CommandResult(spec=spec, executed=live, returncode=0)
        return CommandResult(spec=spec, executed=live, returncode=0)

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        r = self.run(spec, live=live)
        if live and r.returncode != 0:
            raise RuntimeError("fail")
        return r


def test_ensure_labels_creates_and_tolerates_exists():
    r = _FakeRunner()
    ensure_labels(r, "a/b", ["ai:ready", "ai:blocked"], live=True)
    creates = [c for c in r.calls if c[:2] == ("gh", "label")]
    assert any("ai:ready" in c for c in creates)
    assert any("ai:blocked" in c for c in creates)


def test_add_issue_labels_ensures_first():
    r = _FakeRunner()
    add_issue_labels(r, "a/b", 1, ["ai:ready"], live=True)
    assert r.calls[0][:3] == ("gh", "label", "create")
    assert ("gh", "issue", "edit", "1", "--repo", "a/b", "--add-label", "ai:ready") in r.calls


class _RemoveRunner:
    def __init__(self, *, stderr: str, returncode: int = 1) -> None:
        self.stderr = stderr
        self.returncode = returncode
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=self.returncode,
            stderr=self.stderr,
        )


def test_remove_missing_ci_waiting_is_ok():
    r = _RemoveRunner(
        stderr=(
            "failed to update https://github.com/mikolaj92/Fala/issues/164: "
            "'ai:ci-waiting' not found\nfailed to update 164 issue\n"
        )
    )
    remove_issue_labels(r, "mikolaj92/Fala", 164, ["ai:ci-waiting"], live=True)
    assert any("--remove-label" in c for c in ([" ".join(x) for x in r.calls]))


def test_remove_other_gh_error_still_raises():
    r = _RemoveRunner(stderr="HTTP 401: Bad credentials")
    with pytest.raises(RuntimeError, match="HTTP 401"):
        remove_issue_labels(r, "a/b", 1, ["ai:ready"], live=True)

"""ensure_labels creates missing labels before add-label."""

from __future__ import annotations

from lokay.gh_issues import add_issue_labels, ensure_labels
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

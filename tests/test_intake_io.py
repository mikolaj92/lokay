"""Hermetic coverage for intake GitHub I/O (evidence + mutation)."""

from __future__ import annotations

import json

from lokay.config import Config
from lokay.intake import IntakeDecision
from lokay.intake_io import apply_intake, covering_ai_prs, merged_prs
from lokay.models import Issue
from lokay.runner import CommandResult, CommandSpec


class _FakeRunner:
    def __init__(
        self,
        *,
        views: dict[str, object] | None = None,
        lists: dict[str, object] | None = None,
        view_codes: dict[str, int] | None = None,
    ) -> None:
        self.views = views or {}
        self.lists = lists or {}
        self.view_codes = view_codes or {}
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        argv = list(spec.argv)
        if "pr" in argv and "view" in argv:
            num = argv[3]
            if self.view_codes.get(num, 0) != 0:
                return CommandResult(spec=spec, executed=live, returncode=self.view_codes[num])
            payload = self.views.get(num)
            if payload is None:
                return CommandResult(spec=spec, executed=live, returncode=1)
            stdout = payload if isinstance(payload, str) else json.dumps(payload)
            return CommandResult(spec=spec, executed=live, returncode=0, stdout=stdout)
        if "pr" in argv and "list" in argv:
            state = argv[argv.index("--state") + 1]
            return CommandResult(
                spec=spec,
                executed=live,
                returncode=0,
                stdout=json.dumps(self.lists.get(state, [])),
            )
        return CommandResult(spec=spec, executed=live, returncode=0, stdout="{}")

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError("fail")
        return result


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=12,
        title="Implement foo",
        body="Please add feature X with acceptance: does Y when Z happens.",
        labels=["ai:ready"],
        assignees=[],
        url="https://example.com/12",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def test_merged_prs_offline_or_empty():
    runner = _FakeRunner()
    assert merged_prs(runner, "a/b", [1], live=False) == []
    assert merged_prs(runner, "a/b", [], live=True) == []
    assert runner.calls == []


def test_merged_prs_best_effort_selects_merged():
    runner = _FakeRunner(
        views={
            "1": {"number": 1, "state": "OPEN"},
            "3": "{",
            "4": {"number": 4, "mergedAt": "t"},
        },
        view_codes={"2": 1},
    )
    assert merged_prs(runner, "a/b", [1, 2, 3, 4], live=True) == [4]


def test_covering_ai_prs_filters_and_dedupes():
    runner = _FakeRunner(
        lists={
            "open": [
                {"number": 10, "state": "OPEN", "headRefName": "ai/fix/12-foo"},
                {"number": 11, "state": "OPEN", "headRefName": "ai/fix/99-other"},
                {"number": 10, "state": "OPEN", "headRefName": "ai/fix/12-foo"},
            ],
            "merged": [
                {
                    "number": 10,
                    "state": "MERGED",
                    "mergedAt": "t",
                    "headRefName": "ai/fix/12-foo",
                }
            ],
        }
    )
    out = covering_ai_prs(runner, "a/b", 12, branch_prefix="ai/fix", live=True)
    assert [row["number"] for row in out] == [10]
    assert out[0]["head_ref"] == "ai/fix/12-foo"
    assert covering_ai_prs(runner, "a/b", 12, branch_prefix="ai/fix", live=False) == []


def test_apply_intake_skip_and_dry():
    cfg = Config()
    issue = _issue()
    skip = IntakeDecision(decision="skip", reason="parked_frozen")
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, skip, live=True) is False
    ready = IntakeDecision(decision="ready", reason="intake_ok", add_labels=("ai:ready",))
    assert apply_intake(runner, cfg, "a/b", 12, issue, ready, live=False) is False
    assert runner.calls == []


def test_apply_intake_ready_adds_label_and_assignee():
    cfg = Config(assignee="mikolaj92", ready_label="ai:ready")
    issue = _issue(labels=[], assignees=[])
    decision = IntakeDecision(decision="ready", reason="intake_ok")
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert any("--add-label ai:ready" in j for j in joined)
    assert any("--add-assignee mikolaj92" in j for j in joined)


def test_apply_intake_ready_idempotent_when_already_set():
    cfg = Config(assignee="mikolaj92")
    issue = _issue(labels=["ai:ready"], assignees=["mikolaj92"])
    decision = IntakeDecision(decision="ready", reason="intake_ok")
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is False
    assert runner.calls == []


def test_apply_intake_close_mutates():
    cfg = Config()
    issue = _issue(labels=["ai:ready"])
    decision = IntakeDecision(
        decision="close",
        reason="wrong_product_shape",
        remove_labels=("ai:ready",),
        close=True,
        comment="Closed (intake): shape.",
    )
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert any("--remove-label ai:ready" in j for j in joined)
    assert any("issue comment" in j for j in joined)
    assert any("issue close" in j for j in joined)

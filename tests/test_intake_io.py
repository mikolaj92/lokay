"""Hermetic coverage for intake GitHub I/O (evidence + mutation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay import intake_io
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


def test_merged_prs_selects_merged_when_all_evidence_is_available():
    runner = _FakeRunner(
        views={
            "1": {"number": 1, "state": "OPEN"},
            "4": {"number": 4, "mergedAt": "t"},
        }
    )
    assert merged_prs(runner, "a/b", [1, 4], live=True) == [4]


def test_merged_prs_refuses_failed_linked_pr_probe():
    runner = _FakeRunner(
        views={"1": {"number": 1, "state": "OPEN"}}, view_codes={"2": 1}
    )
    try:
        merged_prs(runner, "a/b", [1, 2], live=True)
    except RuntimeError as exc:
        assert "linked PR #2 probe failed" in str(exc)
    else:
        raise AssertionError("unavailable linked PR evidence must fail closed")
    source = Path(intake_io.__file__).read_text(encoding="utf-8")
    assert "Intake linked-PR uncertainty is not an unmerged verdict." in source


def test_merged_prs_refuses_malformed_linked_pr_json():
    runner = _FakeRunner(views={"3": "{"})
    try:
        merged_prs(runner, "a/b", [3], live=True)
    except RuntimeError as exc:
        assert "returned malformed JSON" in str(exc)
    else:
        raise AssertionError("malformed linked PR evidence must fail closed")






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
    assert any("--add-label work:ready" in j for j in joined)
    assert any("--add-assignee mikolaj92" in j for j in joined)


def test_apply_intake_ready_idempotent_when_already_set():
    cfg = Config(assignee="mikolaj92")
    issue = _issue(labels=["ai:ready", "work:ready"], assignees=["mikolaj92"])
    decision = IntakeDecision(decision="ready", reason="intake_ok")
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is False
    assert runner.calls == []


def test_apply_intake_ready_adds_work_ready_when_only_ai_ready():
    cfg = Config(assignee="mikolaj92", ready_label="ai:ready")
    issue = _issue(labels=["ai:ready"], assignees=["mikolaj92"])
    decision = IntakeDecision(decision="ready", reason="intake_ok")
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert any("--add-label work:ready" in j for j in joined)
    assert not any("--add-label ai:ready" in j for j in joined)


def test_apply_intake_blocked_demotes_ready():
    cfg = Config()
    issue = _issue(labels=["ai:ready", "work:ready"])
    decision = IntakeDecision(
        decision="blocked",
        reason="preflight_incident",
        add_labels=("ai:blocked",),
        remove_labels=("ai:ready", "work:ready"),
        comment="Blocked: mill preflight incident.",
    )
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert any("--add-label ai:blocked" in j for j in joined)
    assert any("--remove-label ai:ready" in j for j in joined)
    assert any("--remove-label work:ready" in j for j in joined)


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
    assert not any("issue close" in j for j in joined)


def _close_calls(monkeypatch) -> list[tuple]:
    closes: list[tuple] = []
    monkeypatch.setattr(
        "lokay.intake_io.close_issue",
        lambda *a, **k: closes.append((a, k)),
    )
    return closes


def test_apply_intake_close_open_linked_pr_merged_does_not_close(monkeypatch):
    """reviewkit#205 shape: guessed linked_pr_merged must not close OPEN."""
    cfg = Config()
    issue = _issue(state="OPEN")
    decision = IntakeDecision(
        decision="close",
        reason="linked_pr_merged",
        close=True,
        comment="Closed (intake): linked PR(s) merged.",
    )
    closes = _close_calls(monkeypatch)
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert any("issue comment" in j for j in joined)
    assert closes == []
    assert not any("issue close" in j for j in joined)


def test_apply_intake_close_open_obsolete_does_not_close(monkeypatch):
    """Temida#4995 shape: obsolete_* guess must not close OPEN."""
    cfg = Config()
    issue = _issue(state="OPEN")
    decision = IntakeDecision(
        decision="close",
        reason="obsolete_argus_flow_assumption",
        close=True,
        comment="Closed (intake): obsolete.",
    )
    closes = _close_calls(monkeypatch)
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    assert closes == []
    assert not any("issue close" in " ".join(c) for c in runner.calls)


def test_apply_intake_close_already_closed_may_still_close(monkeypatch):
    """Already-closed is the only exception, same as apply_issue_close."""
    cfg = Config()
    issue = _issue(state="CLOSED", labels=[])
    decision = IntakeDecision(
        decision="close",
        reason="issue_already_closed",
        close=True,
        comment="Closed (intake): already closed upstream.",
    )
    closes = _close_calls(monkeypatch)
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 12, issue, decision, live=True) is True
    assert len(closes) == 1


class _PagedCoveringRunner:
    def __init__(self, pages: dict[int, object], codes: dict[int, int] | None = None) -> None:
        self.pages = pages
        self.codes = codes or {}
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        argv = list(spec.argv)
        page_arg = next(value for value in argv if value.startswith("page="))
        page = int(page_arg.partition("=")[2])
        payload = self.pages.get(page, [])
        stdout = payload if isinstance(payload, str) else json.dumps(payload)
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=self.codes.get(page, 0),
            stdout=stdout,
        )


def test_covering_ai_prs_pages_until_unified_number_boundary(monkeypatch):
    monkeypatch.setattr(intake_io, "COVERING_PR_PAGE_SIZE", 2)
    runner = _PagedCoveringRunner(
        {
            1: [
                {"number": 15, "state": "open", "head": {"ref": "ai/fix/12-foo"}},
                {"number": 14, "state": "closed", "merged_at": "t", "head": {"ref": "ai/fix/99-other"}},
            ],
            2: [
                {"number": 13, "state": "closed", "merged_at": "t", "head": {"ref": "ai/fix/12-old"}},
                {"number": 11, "state": "closed", "merged_at": "t", "head": {"ref": "ai/fix/12-impossible"}},
            ],
        }
    )
    out = covering_ai_prs(runner, "a/b", 12, branch_prefix="ai/fix", live=True)
    assert [row["number"] for row in out] == [15, 13]
    assert len(runner.calls) == 2
    assert all("state=all" in call and "direction=desc" in call for call in runner.calls)


def test_covering_ai_prs_stops_after_first_page_crosses_issue_number(monkeypatch):
    monkeypatch.setattr(intake_io, "COVERING_PR_PAGE_SIZE", 2)
    runner = _PagedCoveringRunner(
        {
            1: [
                {"number": 20, "state": "open", "head": {"ref": "ai/fix/99-other"}},
                {"number": 12, "state": "closed", "merged_at": "t", "head": {"ref": "ai/fix/12-too-old"}},
            ],
            2: [{"number": 11, "state": "open", "head": {"ref": "ai/fix/12-too-old"}}],
        }
    )
    assert covering_ai_prs(runner, "a/b", 12, branch_prefix="ai/fix", live=True) == []
    assert len(runner.calls) == 1


def test_covering_ai_prs_fails_closed_on_unavailable_or_malformed_page():
    failed = _PagedCoveringRunner({1: []}, codes={1: 1})
    with pytest.raises(RuntimeError, match="covering PR page 1 probe failed"):
        covering_ai_prs(failed, "a/b", 12, branch_prefix="ai/fix", live=True)
    malformed = _PagedCoveringRunner({1: {"not": "a list"}})
    with pytest.raises(ValueError, match="covering PR page 1 must be a JSON list"):
        covering_ai_prs(malformed, "a/b", 12, branch_prefix="ai/fix", live=True)

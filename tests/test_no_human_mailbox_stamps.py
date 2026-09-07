"""Contract: factory apply paths never stamp ai:needs-feedback or ai:blocked."""

from __future__ import annotations

from types import SimpleNamespace

from lokay.intake import aggregate_intake, decide_intake
from lokay.intake_io import FORBIDDEN_PROCESS_STAMPS, _sanitize_add_labels, apply_intake
from lokay.models import Issue
from lokay.proc.apply_issue_blocked import apply as apply_blocked
from lokay.proc.apply_issue_manual import apply as apply_manual
from lokay.proc.select_park_stop import MACHINE_PARK_LABEL, select as select_park_stop
from lokay.tasks import MemoryTasks, TaskId, sito_park
from lokay.triage import decide_issue


FORBIDDEN = frozenset({"ai:needs-feedback", "ai:blocked"})


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=1,
        title="Implement useful feature with enough title chars",
        body="A sufficiently detailed body with clear acceptance criteria.\n",
        labels=[],
        assignees=["mikolaj92"],
        url="https://example.test/1",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def test_forbidden_stamps_constant():
    assert FORBIDDEN_PROCESS_STAMPS == FORBIDDEN


def test_sanitize_add_labels_strips_human_mailbox():
    assert _sanitize_add_labels(["ai:frozen", "ai:blocked", "ai:needs-feedback", "x"]) == [
        "ai:frozen",
        "x",
    ]


def test_decide_issue_never_stamps_human_mailbox():
    cases = [
        decide_issue(_issue(title="fix")),
        decide_issue(_issue(body="too short")),
        decide_issue(
            _issue(
                title="Preflight failure deadbeef",
                body="<!-- lokay-preflight:deadbeef -->\nfail",
            )
        ),
        decide_issue(_issue()),
    ]
    for d in cases:
        assert FORBIDDEN.isdisjoint(d.add_labels), d


def test_aggregate_intake_park_and_blocked_use_frozen_only():
    from lokay.intake import CheckResult, BLOCKED, PARK, INCONCLUSIVE

    blocked = aggregate_intake(
        [CheckResult(check="preflight", verdict=BLOCKED, reason="preflight_incident")]
    )
    assert blocked.add_labels == (MACHINE_PARK_LABEL,)
    assert FORBIDDEN.isdisjoint(blocked.add_labels)

    park = aggregate_intake(
        [CheckResult(check="ambiguity", verdict=PARK, reason="title_only_body")]
    )
    assert park.add_labels == (MACHINE_PARK_LABEL,)
    assert FORBIDDEN.isdisjoint(park.add_labels)

    inconclusive = aggregate_intake(
        [CheckResult(check="satisfied", verdict=INCONCLUSIVE, reason="no_clone")]
    )
    assert inconclusive.add_labels == (MACHINE_PARK_LABEL,)
    assert FORBIDDEN.isdisjoint(inconclusive.add_labels)


def test_apply_blocked_stamps_frozen_not_human(monkeypatch):
    labeled: list[list[str]] = []
    removed: list[list[str]] = []

    def _add(runner, repo, issue, labels, *, live):
        labeled.append(list(labels))

    def _remove(runner, repo, issue, labels, *, live):
        removed.append(list(labels))

    monkeypatch.setattr("lokay.proc.apply_issue_blocked.add_issue_labels", _add)
    monkeypatch.setattr("lokay.proc.apply_issue_blocked.remove_issue_labels", _remove)
    cfg = SimpleNamespace(
        ready_label="ai:ready",
        blocked_label="ai:blocked",
        needs_feedback_label="ai:needs-feedback",
    )
    out = apply_blocked(
        runner=object(),
        cfg=cfg,
        repo="o/r",
        issue=1,
        issue_data={"labels": ["ai:ready", "work:ready", "ai:needs-feedback"]},
        live=True,
    )
    assert out["ok"] is True
    assert out["labels"] == [MACHINE_PARK_LABEL]
    assert labeled == [[MACHINE_PARK_LABEL]]
    assert FORBIDDEN.isdisjoint(sum(labeled, []))
    assert "ai:needs-feedback" in removed[0]


def test_apply_manual_and_park_stop_never_human(monkeypatch):
    labeled: list[list[str]] = []

    monkeypatch.setattr(
        "lokay.proc.apply_issue_manual.add_issue_labels",
        lambda *a, **k: labeled.append(list(a[3])),
    )
    monkeypatch.setattr(
        "lokay.proc.apply_issue_manual.comment_issue",
        lambda *a, **k: None,
    )
    decision = {"verdict": "park", "reason": "title_too_short"}
    stop = select_park_stop(decision=decision)
    out = apply_manual(
        runner=object(),
        cfg=SimpleNamespace(needs_feedback_label="ai:needs-feedback"),
        repo="o/r",
        issue=2,
        decision=decision,
        live=True,
        park_stop=stop,
    )
    assert out["labels"] == [MACHINE_PARK_LABEL]
    assert labeled == [[MACHINE_PARK_LABEL]]
    assert FORBIDDEN.isdisjoint(sum(labeled, []))


def test_memory_tasks_mark_never_stamps_human_mailbox():
    source = MemoryTasks(plugin="memory", target="board")
    source.seed(number=1, title="x", labels=["ai:ready"])
    identity = TaskId("memory", "board", 1)
    for kind in ("park", "blocked"):
        out = source.mark(identity, kind)
        assert "ai:frozen" in out.labels
        assert FORBIDDEN.isdisjoint(out.labels)
    parked = sito_park(source, identity, "foreign")
    assert "ai:frozen" in parked.labels
    assert FORBIDDEN.isdisjoint(parked.labels)


def test_apply_intake_strips_forbidden_even_if_decision_smuggles_them():
    from lokay.config import Config
    from lokay.intake import IntakeDecision
    from lokay.runner import CommandResult, CommandSpec

    class _FakeRunner:
        def __init__(self):
            self.calls: list[tuple[str, ...]] = []

        def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
            self.calls.append(spec.argv)
            return CommandResult(spec=spec, executed=live, returncode=0, stdout="{}")

        def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
            return self.run(spec, live=live)

    cfg = Config()
    issue = _issue(labels=["ai:ready"])
    decision = IntakeDecision(
        decision="blocked",
        reason="smuggle",
        add_labels=("ai:blocked", "ai:needs-feedback", "ai:frozen"),
        remove_labels=("ai:ready",),
        comment="x",
    )
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 1, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert any("--add-label ai:frozen" in j for j in joined)
    assert not any("--add-label ai:blocked" in j for j in joined)
    assert not any("--add-label ai:needs-feedback" in j for j in joined)

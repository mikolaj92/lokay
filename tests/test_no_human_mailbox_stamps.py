"""Contract: factory apply paths never stamp limbo labels (frozen/needs-feedback/blocked)."""

from __future__ import annotations

from types import SimpleNamespace

from lokay.intake import aggregate_intake
from lokay.intake_io import FORBIDDEN_PROCESS_STAMPS, _sanitize_add_labels, apply_intake
from lokay.models import Issue
from lokay.proc.apply_issue_blocked import apply as apply_blocked
from lokay.proc.apply_issue_manual import apply as apply_manual
from lokay.proc.select_park_stop import select as select_park_stop
from lokay.tasks import MemoryTasks, TaskId, sito_park
from lokay.triage import decide_issue


FORBIDDEN = frozenset({"ai:needs-feedback", "ai:blocked", "ai:frozen"})


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


def test_sanitize_add_labels_strips_all_limbo():
    assert _sanitize_add_labels(["ai:frozen", "ai:blocked", "ai:needs-feedback", "x"]) == [
        "x",
    ]


def test_decide_issue_never_stamps_limbo():
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


def test_aggregate_intake_park_and_blocked_skip_no_labels():
    from lokay.intake import CheckResult, BLOCKED, PARK, INCONCLUSIVE

    blocked = aggregate_intake(
        [CheckResult(check="preflight", verdict=BLOCKED, reason="preflight_incident")]
    )
    assert blocked.decision == "skip"
    assert blocked.add_labels == ()
    assert FORBIDDEN.isdisjoint(blocked.add_labels)

    park = aggregate_intake(
        [CheckResult(check="ambiguity", verdict=PARK, reason="title_only_body")]
    )
    assert park.decision == "skip"
    assert park.add_labels == ()
    assert FORBIDDEN.isdisjoint(park.add_labels)

    inconclusive = aggregate_intake(
        [CheckResult(check="satisfied", verdict=INCONCLUSIVE, reason="no_clone")]
    )
    assert inconclusive.decision == "skip"
    assert inconclusive.add_labels == ()
    assert FORBIDDEN.isdisjoint(inconclusive.add_labels)


def test_apply_blocked_skips_without_limbo(monkeypatch):
    removed: list[list[str]] = []

    monkeypatch.setattr(
        "lokay.proc.apply_issue_blocked.remove_issue_labels",
        lambda *a, **k: removed.append(list(a[3])),
    )
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
        issue_data={"labels": ["ai:ready", "work:ready", "ai:needs-feedback", "ai:frozen"]},
        live=True,
    )
    assert out["ok"] is True
    assert out["labels"] == []
    assert "ai:needs-feedback" in removed[0]
    assert "ai:frozen" in removed[0]


def test_apply_manual_and_park_stop_never_limbo(monkeypatch):
    comments: list[str] = []

    monkeypatch.setattr(
        "lokay.proc.apply_issue_manual.comment_issue",
        lambda *a, **k: comments.append(a[3]),
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
    assert out["labels"] == []
    assert out["route"] == "skip"
    assert FORBIDDEN.isdisjoint(out["labels"])
    assert comments and "title_too_short" in comments[0]


def test_memory_tasks_mark_never_stamps_limbo():
    source = MemoryTasks(plugin="memory", target="board")
    source.seed(number=1, title="x", labels=["ai:ready", "ai:frozen"])
    identity = TaskId("memory", "board", 1)
    for kind in ("park", "blocked"):
        out = source.mark(identity, kind)
        assert FORBIDDEN.isdisjoint(out.labels)
        assert "ai:ready" not in out.labels
    parked = sito_park(source, identity, "foreign")
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
        decision="skip",
        reason="smuggle",
        add_labels=("ai:blocked", "ai:needs-feedback", "ai:frozen"),
        remove_labels=("ai:ready",),
        comment="x",
    )
    runner = _FakeRunner()
    assert apply_intake(runner, cfg, "a/b", 1, issue, decision, live=True) is True
    joined = [" ".join(c) for c in runner.calls]
    assert not any("--add-label ai:frozen" in j for j in joined)
    assert not any("--add-label ai:blocked" in j for j in joined)
    assert not any("--add-label ai:needs-feedback" in j for j in joined)

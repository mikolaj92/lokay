"""Hermetic issue ledger stage transitions (no live gh)."""

from __future__ import annotations

import pytest

from lokay.stage_ledger import (
    LABEL_CI_WAITING,
    LABEL_IMPLEMENTING,
    LABEL_PR_OPEN,
    LABEL_READY,
    LABEL_REPAIRING,
    LEDGER_ACTIVE_LABELS,
    NEW_LEDGER_LABELS,
    current_ledger_stage,
    plan_stage_transition,
)
from lokay.triage import decision_labels, is_undecided


def test_new_ledger_labels_budget():
    assert len(NEW_LEDGER_LABELS) <= 6
    assert set(NEW_LEDGER_LABELS) == {
        LABEL_PR_OPEN,
        LABEL_CI_WAITING,
        LABEL_REPAIRING,
    }


def test_exclusive_ready_clears_in_flight():
    plan = plan_stage_transition("ready")
    assert plan.add_labels == (LABEL_READY,)
    assert LABEL_IMPLEMENTING in plan.remove_labels
    assert LABEL_PR_OPEN in plan.remove_labels
    assert LABEL_CI_WAITING in plan.remove_labels
    assert LABEL_REPAIRING in plan.remove_labels
    assert LABEL_READY not in plan.remove_labels


def test_implementing_drops_ready():
    plan = plan_stage_transition("implementing")
    assert plan.add_labels == (LABEL_IMPLEMENTING,)
    assert LABEL_READY in plan.remove_labels
    assert LABEL_PR_OPEN in plan.remove_labels


def test_pr_open_and_ci_waiting_and_repairing():
    assert plan_stage_transition("pr-open").add_labels == (LABEL_PR_OPEN,)
    assert plan_stage_transition("ci-waiting").add_labels == (LABEL_CI_WAITING,)
    assert plan_stage_transition("repairing").add_labels == (LABEL_REPAIRING,)
    clear = plan_stage_transition("clear")
    assert clear.add_labels == ()
    assert set(clear.remove_labels) == {
        LABEL_READY,
        LABEL_IMPLEMENTING,
        LABEL_PR_OPEN,
        LABEL_CI_WAITING,
        LABEL_REPAIRING,
    }


def test_receipt_optional():
    assert plan_stage_transition("implementing", receipt=False).receipt is None
    assert "implementing" in (plan_stage_transition("implementing", receipt=True).receipt or "")


def test_unknown_stage_raises():
    with pytest.raises(ValueError, match="unknown ledger stage"):
        plan_stage_transition("nope")


def test_current_ledger_stage_prefers_repairing():
    assert (
        current_ledger_stage(
            [LABEL_READY, LABEL_PR_OPEN, LABEL_REPAIRING, LABEL_CI_WAITING]
        )
        == "repairing"
    )
    assert current_ledger_stage([LABEL_READY]) == "ready"
    assert current_ledger_stage([]) is None


def test_ledger_labels_leave_inbox():
    for label in LEDGER_ACTIVE_LABELS:
        assert not is_undecided([label])
        assert label in decision_labels()


def test_stage_label_atom_dry_run_envelope(tmp_path, monkeypatch, capsys):
    import json

    from lokay.proc import stage_label as atom
    from lokay.runner import CommandResult

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
mode: dry-run
github:
  assignee: mikolaj92
repos: []
""",
        encoding="utf-8",
    )
    calls: list[tuple] = []

    class _R:
        def run(self, spec, *, live):
            calls.append((tuple(spec.argv), live))
            return CommandResult(spec=spec, executed=live, returncode=0)

        def run_checked(self, spec, *, live):
            return self.run(spec, live=live)

    monkeypatch.setattr(atom, "runner", lambda: _R())
    code = atom.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "a/b",
            "--issue",
            "7",
            "--stage",
            "implementing",
        ]
    )
    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert env["planned"] is True
    assert env["applied"] is False
    assert env["stage"] == "implementing"
    assert env["add_labels"] == [LABEL_IMPLEMENTING]
    assert LABEL_READY in env["remove_labels"]
    # dry-run still plans through gh helpers with live=False
    assert calls and all(live is False for _, live in calls)

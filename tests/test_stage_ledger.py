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
    assert NEW_LEDGER_LABELS == ()


def test_exclusive_ready_clears_in_flight():
    plan = plan_stage_transition("ready")
    assert plan.add_labels == (LABEL_READY, "work:ready")
    assert LABEL_IMPLEMENTING in plan.remove_labels
    assert LABEL_PR_OPEN in plan.remove_labels
    assert LABEL_CI_WAITING in plan.remove_labels
    assert LABEL_REPAIRING in plan.remove_labels
    assert LABEL_READY not in plan.remove_labels


def test_inflight_stage_names_keep_ready():
    for name in ("implementing", "pr-open", "ci-waiting", "repairing"):
        plan = plan_stage_transition(name)
        assert plan.stage == "ready"
        assert plan.add_labels == (LABEL_READY, "work:ready")
        assert LABEL_IMPLEMENTING in plan.remove_labels
        assert LABEL_PR_OPEN in plan.remove_labels
        assert LABEL_READY not in plan.remove_labels


def test_clear_strips_ready_and_cache():
    clear = plan_stage_transition("clear")
    assert clear.add_labels == ()
    assert set(clear.remove_labels) == {
        LABEL_READY,
        "work:ready",
        LABEL_IMPLEMENTING,
        LABEL_PR_OPEN,
        LABEL_CI_WAITING,
        LABEL_REPAIRING,
    }


def test_receipt_optional():
    assert plan_stage_transition("ready", receipt=False).receipt is None
    assert "ready" in (plan_stage_transition("ready", receipt=True).receipt or "")
    assert plan_stage_transition("implementing", receipt=True).receipt is not None


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


def _stage_cfg(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mode: dry-run\nrepos: []\n", encoding="utf-8")
    return cfg


def test_stage_prepare_keeps_ready_labels_for_inflight(tmp_path):
    from lokay.proc.prepare_stage_transition import prepare

    out = prepare(
        config_path=str(_stage_cfg(tmp_path)),
        live=False,
        repo="a/b",
        issue=7,
        stage="implementing",
        receipt=False,
        comment="",
    )
    assert out["stage"] == "ready"
    assert LABEL_READY not in out["remove_labels"]
    assert out["live"] is False


def test_stage_clear_may_remove_ready_after_merge(tmp_path):
    from lokay.proc.prepare_stage_transition import prepare

    out = prepare(
        config_path=str(_stage_cfg(tmp_path)),
        live=False,
        repo="a/b",
        issue=7,
        stage="clear",
        receipt=False,
        comment="",
    )
    assert LABEL_READY in out["remove_labels"]


def test_stage_closed_terminal_skips_all_effects():
    from lokay.proc.stage_label_terminal import terminal

    out = terminal(
        {
            "repo": "a/b",
            "issue": 7,
            "stage": "ready",
            "add_labels": ["ai:ready"],
            "remove_labels": ["old"],
        },
        {"issue_state": "CLOSED"},
        {"route": "terminal", "reason": "issue_closed", "issue_state": "CLOSED"},
        {},
        {},
        {},
    )["result"]
    assert out["skipped"] is True
    assert out["applied"] is False
    assert out["receipt"] is False

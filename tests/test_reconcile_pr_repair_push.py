from __future__ import annotations

import hashlib
import json

from lokay.proc import pr_repair_receipts
from lokay.proc.reconcile_pr_repair_push import reconcile_pending


def _pending_intent(repo: str, pr: int, branch: str, state_dir):
    task = {"repo": repo, "type": "Issue", "state": "OPEN", "number": 42}
    digest = hashlib.sha256(json.dumps(
        task, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    intent = pr_repair_receipts.build_push_intent(
        repo=repo, pr=pr, branch=branch, repair_kind="review",
        start_head_sha="a" * 40, target_head_sha="b" * 40,
        reviewed_head_sha="a" * 40, task=task,
        findings=[{"path": "a.py", "content": "bug"}],
        task_identity_sha256=digest, review_result_sha256="e" * 64,
    )
    assert pr_repair_receipts.prepare_push_intent(
        repo=repo, pr=pr, intent=intent, budget=2, state_dir=state_dir,
    )["route"] == "recorded"
    assert pr_repair_receipts.mark_push_attempted(
        repo=repo, pr=pr, intent_sha256=intent["intent_sha256"], state_dir=state_dir,
    )["route"] == "ready"
    return intent


def test_no_pending_intent_opens_review_only_for_valid_selected_pr(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )
    selected = {
        "ok": True, "route": "pr", "repo": "o/r", "pr": 9,
        "branch": "ai/fix/9-x",
    }
    out = reconcile_pending(config_path="config.yaml", live=True, selection=selected)
    assert out["route"] == "review"
    assert out["recovered"] == []
    no_pr = reconcile_pending(
        config_path="config.yaml", live=True,
        selection={"ok": True, "route": "none", "reason": "no_open_pr"},
    )
    assert no_pr["route"] == "no_pr"
    listed_failed = reconcile_pending(
        config_path="config.yaml", live=True,
        selection={"ok": False, "route": "none", "reason": "list_failed"},
    )
    assert listed_failed["route"] == "fail_closed"
    assert listed_failed["reason"] == "list_failed"


def test_dry_run_does_not_confirm_pending_push(monkeypatch, tmp_path):
    _pending_intent("o/r", 9, "ai/fix/9-x", tmp_path)
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )

    out = reconcile_pending(
        config_path="config.yaml", live=False,
        selection={"ok": True, "route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_push_reconciliation_requires_live"
    assert pr_repair_receipts.read("o/r", 9, state_dir=tmp_path)["pending_push"]


def test_recovered_intent_confirms_before_triage(monkeypatch, tmp_path):
    intent = _pending_intent("o/r", 9, "ai/fix/9-x", tmp_path)
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )
    monkeypatch.setattr(
        "lokay.proc.probe_pr_state.probe",
        lambda **_kwargs: {
            "ok": True, "route": "open", "state": "OPEN",
            "head_ref": "ai/fix/9-x", "head_ref_sha": "b" * 40,
            "head_repo": "o/r",
        },
    )

    out = reconcile_pending(
        config_path="config.yaml", live=True,
        selection={"ok": True, "route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
    )

    assert out["route"] == "recovered"
    assert out["recovered"][0]["head_sha"] == "b" * 40
    assert out["recovered"][0]["intent_sha256"] == intent["intent_sha256"]
    stored = pr_repair_receipts.read("o/r", 9, state_dir=tmp_path)
    assert stored["pending_push"] is None
    assert stored["last_intent_sha256"] == intent["intent_sha256"]
    assert stored["attempts"] == 1


def test_remote_identity_mismatch_fails_closed(monkeypatch, tmp_path):
    _pending_intent("o/r", 9, "ai/fix/9-x", tmp_path)
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )
    monkeypatch.setattr(
        "lokay.proc.probe_pr_state.probe",
        lambda **_kwargs: {
            "ok": True, "route": "open", "state": "OPEN",
            "head_ref": "different-branch", "head_ref_sha": "b" * 40,
            "head_repo": "o/r",
        },
    )

    out = reconcile_pending(
        config_path="config.yaml", live=True,
        selection={"ok": True, "route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_push_remote_identity_mismatch"
    assert pr_repair_receipts.read("o/r", 9, state_dir=tmp_path)["pending_push"]


def test_remote_probe_unavailable_fails_closed(monkeypatch, tmp_path):
    _pending_intent("o/r", 9, "ai/fix/9-x", tmp_path)
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )
    monkeypatch.setattr(
        "lokay.proc.probe_pr_state.probe",
        lambda **_kwargs: {"ok": True, "route": "unavailable", "probe_failed": True},
    )

    out = reconcile_pending(
        config_path="config.yaml", live=True,
        selection={"ok": True, "route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
    )
    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_push_remote_identity_unavailable"


def test_live_probe_is_never_performed_when_receipts_are_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )
    monkeypatch.setattr(
        "lokay.proc.probe_pr_state.probe",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no pending intent")),
    )

    selected = {"ok": True, "route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"}
    empty = {"ok": True, "route": "none", "reason": "no_open_pr"}
    assert reconcile_pending(config_path="config.yaml", live=True, selection=selected)["route"] == "review"
    assert reconcile_pending(config_path="config.yaml", live=True, selection=empty)["route"] == "no_pr"

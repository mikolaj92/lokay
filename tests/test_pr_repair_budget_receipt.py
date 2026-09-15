"""Per-PR pr_repair lifetime K via durable receipt (#1035)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.run_parent_pr_repair_subflow import _repair_meta, run as run_parent
from lokay.proc.run_pr_repair_department import run as run_department
from lokay.proc.select_pr_repair_department import select


def _repairable(**extra: object) -> dict:
    task = {"repo":"o/r", "type":"Issue", "state":"OPEN", "number":42,
            "title":"task", "body":"acceptance", "url":"https://github.com/o/r/issues/42"}
    task_digest = hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    finding = {"path":"src/a.py", "start_line":1, "end_line":1,
               "severity":"high", "category":"bug", "content":"defect"}
    review = {"verdict":"request_changes", "task":task, "findings":[finding],
              "reviewed_head_sha":"a"*40, "task_identity_sha256":task_digest,
              "review_result_sha256":"e"*64}
    return {
        "triage": {
            "repairable": True,
            "reason": "review_requested_changes",
            "repair_kind": "review",
            "review": review,
        },
        "review": review,
        "task": task,
        "findings": [finding],
        "reviewed_head_sha": "a"*40,
        "task_identity_sha256": task_digest,
        "repair_kind": "review",
        "repair_start_head_sha": "a"*40,
        "verdict": "repair",
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-x",
        **extra,
    }


def test_ci_repair_confirmation_requires_a_new_sha_from_the_start_head() -> None:
    result = {"ok": True, "result": {
        "repo": "o/r", "pr": 9, "repaired": True, "published": True,
        "terminal": "publish", "head_sha": "a" * 40,
    }}
    *_, confirmed, _ = _repair_meta(
        result, {"kind": "ci", "start_head_sha": "a" * 40},
    )
    assert confirmed is False


def test_per_pr_budget_uses_request_changes_cap_not_fleet_tick_limit(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_request_changes_per_pr: 2
  max_repairs_per_tick: 1
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
""",
        encoding="utf-8",
    )
    assert receipts.resolve_budget(str(cfg)) == 2


def test_stamp_increments_and_parks(tmp_path: Path) -> None:
    first = receipts.stamp(
        "o/r", 9, state_dir=tmp_path, budget=1,
        head_sha="b" * 40, reviewed_sha="a" * 40, terminal="publish",
    )
    assert first["attempts"] == 1
    assert first["budget"] == 1
    assert first["parked"] is True
    assert first["last_head_sha"] == "b" * 40
    second = receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    assert second["attempts"] == 2
    assert second["parked"] is True
    loaded = receipts.read("o/r", 9, state_dir=tmp_path)
    assert loaded["attempts"] == 2
    assert receipts.clear("o/r", 9, state_dir=tmp_path) is True
    assert receipts.read("o/r", 9, state_dir=tmp_path) == {}


def test_receipt_rejects_explicit_null_confirmed_identity(tmp_path: Path) -> None:
    path = receipts.receipt_path("o/r", 9, state_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "repo": "o/r", "pr": 9, "attempts": 1, "budget": 2,
        "parked": False, "pending_push": None,
        "last_head_sha": None,
        "last_intent_sha256": "c" * 64,
        "last_branch": "ai/fix/9-x", "last_repair_kind": "review",
        "last_terminal": "publish",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="identity is incomplete"):
        receipts.read("o/r", 9, state_dir=tmp_path)


def test_malformed_receipt_is_not_treated_as_an_empty_repair_budget(tmp_path: Path) -> None:
    path = receipts.receipt_path("o/r", 9, state_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{truncated", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed"):
        receipts.read("o/r", 9, state_dir=tmp_path)


def test_receipt_rejects_duplicate_pushed_head_sha(tmp_path: Path) -> None:
    receipts.stamp(
        "o/r", 9, state_dir=tmp_path, budget=2,
        reviewed_sha="a" * 40, head_sha="b" * 40, terminal="publish",
    )
    with pytest.raises(ValueError, match="already records"):
        receipts.stamp(
            "o/r", 9, state_dir=tmp_path, budget=2,
            reviewed_sha="a" * 40, head_sha="b" * 40,
        )


def test_concurrent_receipt_updates_do_not_lose_confirmed_attempts(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    workers, updates_per_worker = 8, 12
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(
            lambda worker: [
                receipts.stamp(
                    "o/r", 9, state_dir=tmp_path,
                    budget=workers * updates_per_worker, terminal="publish",
                    head_sha=f"{worker * updates_per_worker + update + 1:040x}",
                    reviewed_sha=f"{worker * updates_per_worker + update + 101:040x}",
                )
                for update in range(updates_per_worker)
            ],
            range(workers),
        ))

    stored = receipts.read("o/r", 9, state_dir=tmp_path)
    assert stored["attempts"] == workers * updates_per_worker


def test_select_gates_when_attempts_exhausted(tmp_path: Path) -> None:
    receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    out = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
        budget=1,
    )
    assert out["route"] == "fail_closed"
    assert out["reason"] == "pr_repair_budget_exhausted"
    assert out["parked"] is True
    assert out["attempts"] == 1
    assert out["budget"] == 1
    assert out["repairable"] is True
    assert "needs_human" not in out


def test_select_routes_repair_when_receipt_empty(tmp_path: Path) -> None:
    out = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
        budget=1,
    )
    assert out["route"] == "repair"
    assert out["attempts"] == 0
    assert out["parked"] is False
    assert "needs_human" not in out


def test_repair_worktree_add_recovers_pushed_intent_after_parent_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, pr, branch = "o/r", 9, "ai/fix/9-x"
    selected = _repairable()
    review = selected["review"]
    intent = receipts.build_push_intent(
        repo=repo, pr=pr, branch=branch, repair_kind="review",
        start_head_sha="a" * 40, target_head_sha="b" * 40,
        reviewed_head_sha="a" * 40, task=selected["task"],
        findings=selected["findings"],
        task_identity_sha256=review["task_identity_sha256"],
        review_result_sha256=review["review_result_sha256"],
    )
    assert receipts.prepare_push_intent(
        repo=repo, pr=pr, intent=intent, budget=2, state_dir=tmp_path,
    )["route"] == "recorded"
    assert receipts.mark_push_attempted(
        repo=repo, pr=pr, intent_sha256=intent["intent_sha256"],
        state_dir=tmp_path,
    )["route"] == "ready"

    worktree = tmp_path / "repair-worktree"
    (worktree / ".git").parent.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: /private/repair", encoding="utf-8")
    monkeypatch.setattr(
        "lokay.proc.worktree_add.load_cfg",
        lambda _args: type("Config", (), {"repos": [type("Repo", (), {
            "name": repo, "clone_path": tmp_path / "clone",
        })()], "worktrees_root": tmp_path,
        "config_path": tmp_path / "config.yaml"})(),
    )
    monkeypatch.setattr(
        "lokay.proc.worktree_add.runner",
        lambda: object(),
    )
    monkeypatch.setattr("lokay.proc.worktree_add.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        "lokay.git_worktree.ensure_repair_worktree",
        lambda *_args, **_kwargs: worktree,
    )
    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: {"headRepository": {"nameWithOwner": repo}},
    )
    monkeypatch.setattr(
        "lokay.proc.worktree_add.verify_repair_start_identity",
        lambda *_args, **_kwargs: {
            "route": "ready", "repair_start_head_sha": "a" * 40,
            "worktree_head_sha": "a" * 40,
        },
    )
    from lokay.proc.worktree_add import main as worktree_add_main

    worktree_result = worktree_add_main([
        "--config", str(tmp_path / "config.yaml"), "--live",
        "--repo", repo, "--branch", branch,
        "--pr", str(pr), "--repair-start-head-sha", "a" * 40,
    ])
    assert worktree_result == 0

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
repos:
  - name: {repo}
    clone_path: {tmp_path / 'clone'}
""",
        encoding="utf-8",
    )
    remote_reads: list[tuple[str, int, str | None]] = []

    def read_remote(*, repo: str, pr: int, live: bool, config_path: str | None = None):
        assert live is True
        remote_reads.append((repo, pr, config_path))
        return {
            "ok": True, "route": "open", "state": "OPEN",
            "head_ref": branch, "head_ref_sha": "b" * 40,
            "head_repo": repo,
        }

    monkeypatch.setattr("lokay.proc.probe_pr_state.probe", read_remote)
    selected_route = select(
        {"repo": repo, "pr": pr, "repair_kind": "review",
         "triage": {"repairable": False, "repair_kind": "review"}},
        enabled=True,
        triage_ran=True,
        config_path=str(cfg),
        live=True,
        state_dir=tmp_path,
        budget=2,
    )

    stored = receipts.read(repo, pr, state_dir=tmp_path)
    assert selected_route["route"] == "skip", selected_route
    assert selected_route["reason"] == "repair_push_recovered"
    assert selected_route["attempts"] == 1
    assert selected_route["last_head_sha"] == "b" * 40
    assert stored["attempts"] == 1
    assert stored["last_reviewed_sha"] == "a" * 40
    assert stored["last_head_sha"] == "b" * 40
    assert stored["pending_push"] is None
    assert remote_reads == [(repo, pr, str(cfg))]


def test_repair_selector_fails_closed_on_unattempted_or_unavailable_push_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = _repairable()
    review = selected["review"]
    intent = receipts.build_push_intent(
        repo="o/r", pr=9, branch="ai/fix/9-x", repair_kind="review",
        start_head_sha="a" * 40, target_head_sha="b" * 40,
        reviewed_head_sha="a" * 40, task=selected["task"],
        findings=selected["findings"],
        task_identity_sha256=review["task_identity_sha256"],
        review_result_sha256=review["review_result_sha256"],
    )
    receipts.prepare_push_intent(
        repo="o/r", pr=9, intent=intent, budget=2, state_dir=tmp_path,
    )

    unattempted = select(
        {"repo": "o/r", "pr": 9}, enabled=True, triage_ran=True, live=True,
        state_dir=tmp_path, budget=2,
    )
    assert unattempted["route"] == "fail_closed"
    assert unattempted["reason"] == "repair_push_attempt_not_recorded"
    assert receipts.read("o/r", 9, state_dir=tmp_path)["attempts"] == 0

    assert receipts.mark_push_attempted(
        repo="o/r", pr=9, intent_sha256=intent["intent_sha256"],
        state_dir=tmp_path,
    )["route"] == "ready"
    unavailable = select(
        {"repo": "o/r", "pr": 9}, enabled=True, triage_ran=True, live=True,
        state_dir=tmp_path, budget=2,
    )
    assert unavailable["route"] == "fail_closed"
    assert unavailable["reason"] == "repair_push_remote_identity_unavailable"
    assert receipts.read("o/r", 9, state_dir=tmp_path)["attempts"] == 0


def test_repair_selector_fails_closed_on_remote_push_identity_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = _repairable()
    review = selected["review"]
    intent = receipts.build_push_intent(
        repo="o/r", pr=9, branch="ai/fix/9-x", repair_kind="review",
        start_head_sha="a" * 40, target_head_sha="b" * 40,
        reviewed_head_sha="a" * 40, task=selected["task"],
        findings=selected["findings"],
        task_identity_sha256=review["task_identity_sha256"],
        review_result_sha256=review["review_result_sha256"],
    )
    receipts.prepare_push_intent(
        repo="o/r", pr=9, intent=intent, budget=2, state_dir=tmp_path,
    )
    receipts.mark_push_attempted(
        repo="o/r", pr=9, intent_sha256=intent["intent_sha256"],
        state_dir=tmp_path,
    )
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
repos:
  - name: o/r
    clone_path: {tmp_path / 'clone'}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lokay.proc.probe_pr_state.probe",
        lambda **_kwargs: {
            "ok": True, "route": "open", "state": "OPEN",
            "head_ref": "some/other-branch", "head_ref_sha": "b" * 40,
            "head_repo": "o/r",
        },
    )

    out = select(
        {"repo": "o/r", "pr": 9,
         "triage": {"repairable": False}},
        enabled=True, triage_ran=True, config_path=str(cfg), live=True,
        state_dir=tmp_path, budget=2,
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_push_remote_identity_mismatch"
    assert receipts.read("o/r", 9, state_dir=tmp_path)["attempts"] == 0
    assert receipts.read("o/r", 9, state_dir=tmp_path)["pending_push"]


def test_dry_run_never_consumes_confirmed_push_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_repairs_per_tick: 1
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
    enabled: true
""",
        encoding="utf-8",
    )
    calls: list[dict] = []

    task = _repairable()["task"]
    findings = _repairable()["findings"]
    review = _repairable()["review"]

    def fake_compose(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return {"ok": True, "result": {
            "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x",
            "repaired": True, "published": True,
            "terminal": "publish", "reviewed_head_sha": "a" * 40, "head_sha": "b" * 40,
            "task": task, "findings": findings,
            "task_identity_sha256": review["task_identity_sha256"],
            "review_result_sha256": review["review_result_sha256"],
        }}

    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair", fake_compose
    )
    selected = {
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-x",
        "review": _repairable()["review"],
        "task": _repairable()["task"],
        "findings": _repairable()["findings"],
        "reviewed_head_sha": "a"*40,
        "task_identity_sha256": review["task_identity_sha256"],
        "review_result_sha256": review["review_result_sha256"],
        "repair_kind": "review",
    }
    out = run_parent(selected, config_path=str(cfg), live=False)
    assert out["route"] == "planned"
    assert out["attempts"] == 0
    assert out["budget"] == 2
    assert out["parked"] is False
    assert len(calls) == 1
    stored = receipts.read("o/r", 9, state_dir=tmp_path)
    assert stored == {}

    gated = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        config_path=str(cfg),
    )
    assert gated["route"] == "repair"


def test_parent_fails_closed_before_repair_when_canonical_task_has_drifted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_request_changes_per_pr: 2
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
""",
        encoding="utf-8",
    )
    called = []
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair",
        lambda **kwargs: called.append(kwargs) or {"ok": True},
    )
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow._review_task_is_current",
        lambda *_args, **_kwargs: False,
    )
    selected = _repairable()

    out = run_parent(selected, config_path=str(cfg), live=True)

    assert out["route"] == "fail_closed"
    assert out["reason"] == "review_repair_task_identity_drift"
    assert called == []


def test_parent_forwards_exact_review_task_and_findings_to_repair_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_request_changes_per_pr: 2
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
""",
        encoding="utf-8",
    )
    task = {"repo":"o/r", "type":"Issue", "state":"OPEN", "number":42,
            "title":"task", "body":"full acceptance body", "url":"https://github.com/o/r/issues/42"}
    finding = {"path":"src/a.py", "start_line":2, "end_line":2, "severity":"high", "category":"bug", "content":"defect"}
    task_digest = hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    review = {"verdict":"request_changes", "task":task, "findings":[finding],
              "reviewed_head_sha":"a"*40, "task_identity_sha256":task_digest,
              "review_result_sha256":"e"*64}
    calls = []
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair",
        lambda **kwargs: calls.append(kwargs) or {"ok":False, "terminal":"fail_closed"},
    )

    run_parent(
        {"route":"repair", "repo":"o/r", "pr":9, "branch":"ai/fix/42-task", "review":review,
         "task":task, "findings":[finding], "reviewed_head_sha":"a"*40,
         "task_identity_sha256":review["task_identity_sha256"],
         "review_result_sha256":review["review_result_sha256"], "repair_kind":"review",
         "repair_start_head_sha":"a"*40},
        config_path=str(cfg), live=False,
    )

    assert calls[0]["task"] == task
    assert calls[0]["findings"] == [finding]
    assert calls[0]["reviewed_head_sha"] == "a"*40
    assert calls[0]["task_identity_sha256"] == review["task_identity_sha256"]
    assert calls[0]["review_result_sha256"] == review["review_result_sha256"]
    assert calls[0]["repair_kind"] == "review"
    assert calls[0]["repair_start_head_sha"] == "a"*40


def test_exhausted_select_does_not_call_compose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    selected = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
        budget=1,
    )
    assert selected["route"] == "fail_closed"

    def boom(**_kwargs: object) -> dict:
        raise AssertionError("compose must not run when budget exhausted")

    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair", boom
    )
    out = run_department(selected, config_path=None, live=False)
    assert out["route"] == "fail_closed"
    assert out["reason"] == "pr_repair_budget_exhausted"
    assert out["parked"] is True
    assert "needs_human" not in out


def test_run_does_not_consume_budget_for_unconfirmed_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_request_changes_per_pr: 2
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair",
        lambda **_kwargs: {"ok": False, "terminal": "fail_closed"},
    )

    out = run_parent(
        {"repo": "o/r", "pr": 3, "branch": "ai/fix/3-x", "review": {}},
        config_path=str(cfg), live=False,
    )

    assert out["route"] == "fail_closed"
    assert out["attempts"] == 0
    assert receipts.read("o/r", 3, state_dir=tmp_path) == {}


def test_run_stamps_on_compose_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
    enabled: true
""",
        encoding="utf-8",
    )

    def fake_compose(**_kwargs: object) -> dict:
        return {"ok": False, "error": "agent_failed", "terminal": "fail_closed"}

    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair", fake_compose
    )
    out = run_parent(
        {"repo": "o/r", "pr": 3, "branch": "ai/fix/3-x", "review": {}},
        config_path=str(cfg),
        live=False,
    )
    assert out["route"] == "fail_closed"
    assert out["attempts"] == 0
    assert out["parked"] is False
    assert receipts.read("o/r", 3, state_dir=tmp_path) == {}

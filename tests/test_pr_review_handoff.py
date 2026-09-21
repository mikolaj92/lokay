"""Authored conduction must carry review findings into repair receipts."""

from pathlib import Path
import tomllib

import pytest

from lokay.organ.pr_outcome import handle_pr_outcome


@pytest.mark.parametrize("atom", ["pr_repair_verdict", "summarize_pr_triage"])
def test_authored_review_handoff_retains_blockers(atom):
    root = Path(__file__).resolve().parents[1]
    package = tomllib.loads((root / "fala/lokay.fala-package.toml").read_text())
    graph = next(p for p in package["correlation_paths"] if p["id"] == "pr_triage")
    node = next(n for n in graph["effectors"] if n["id"] == atom)
    task = {"repo": "o/r", "type": "Issue", "state": "OPEN", "number": 9,
            "title": "Task", "body": "Acceptance", "url": "https://github.com/o/r/issues/9"}
    finding = {"path": "src/a.py", "start_line": 2, "end_line": 2,
               "category": "bug", "severity": "high", "content": "Root mount hides health endpoint"}
    import hashlib, json
    task_digest = hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    decision = {"verdict": "request_changes", "blocking": ["Root mount hides health endpoint"],
                "task": task, "findings": [finding], "reviewed_head_sha": "a" * 40,
                "task_identity_sha256": task_digest, "review_result_sha256": "b" * 64}
    available = {
        "publish_pr_review": {"ok": True, "decision": decision},
        "select_pr_triage_outcome": {
            "route": "repair", "repair_kind": "review",
            "repair_start_head_sha": "a" * 40,
        },
    }
    if atom == "summarize_pr_triage":
        available["pr_repair_verdict"] = handle_pr_outcome(
            "pr_repair_verdict", {}, available, {}
        )
    upstream = {key: available.get(key, {}) for key in node["conduction"]}
    result = handle_pr_outcome(atom, {}, upstream, {})
    assert result is not None
    receipt = result.get("result", result)
    assert receipt["review"] == decision
    assert receipt["task"] == task
    assert receipt["findings"] == [finding]
    assert receipt["review_result_sha256"] == "b" * 64


def test_two_repairs_force_fresh_sha_three_review_before_one_merge(monkeypatch, tmp_path):
    import hashlib
    import json
    from types import SimpleNamespace

    from lokay.config import Config, RepoConfig
    from lokay.organ.pr_outcome import handle_pr_outcome
    from lokay.pr_review import PrReviewDecision, decide_review_merge, format_review_marker
    from lokay.proc import pr_merge
    from lokay.proc.run_parent_pr_repair_subflow import run as run_parent_repair
    from lokay.proc.select_pr_repair_department import select as select_repair
    from lokay.proc.select_pr_triage_outcome import select as select_triage_outcome
    from lokay.proc.review_repair_gate import route_review_repair
    from lokay.review_boundary import resolve_sha_review

    repo, pr, branch = "acme/demo", 84, "ai/fix/42-demo"
    task = {
        "repo": repo, "type": "Issue", "state": "OPEN", "number": 42,
        "title": "Prevent invalid save", "body": "Reject blank IDs.",
        "url": f"https://github.com/{repo}/issues/42",
    }
    task_digest = hashlib.sha256(
        json.dumps(task, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    findings = [{
        "path": "src/demo.py", "start_line": 12, "end_line": 13,
        "category": "bug", "severity": "high", "content": "Blank IDs reach persistence.",
    }]
    sha1, sha2, sha3 = (letter * 40 for letter in ("a", "b", "c"))
    comments = []
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow._review_task_is_current",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow._remote_head",
        lambda *_args, **_kwargs: current_remote[0],
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_budget", lambda _path: 2,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.resolve_state_dir", lambda _path: tmp_path,
    )
    current_remote = [sha2]
    current_head = sha1

    for reviewed_sha, pushed_sha in ((sha1, sha2), (sha2, sha3)):
        result_digest = hashlib.sha256(reviewed_sha.encode()).hexdigest()
        decision = {
            "verdict": "request_changes", "secrets": False, "task": task,
            "findings": findings, "reviewed_head_sha": reviewed_sha,
            "task_identity_sha256": task_digest,
            "review_result_sha256": result_digest,
        }
        verdict = handle_pr_outcome(
            "pr_repair_verdict", {},
            {
                "select_pr_triage_outcome": {
                    "route": "repair", "repair_kind": "review",
                    "reason": "review_requested_changes",
                    "repair_start_head_sha": reviewed_sha,
                },
                "publish_pr_review": {"decision": decision},
            },
            {"repo": repo, "pr_number": pr, "branch": branch, "live": False},
        )
        triage = {
            "repairable": True, "repair_kind": "review", "review": decision,
            "task": task, "findings": findings,
            "reviewed_head_sha": reviewed_sha,
            "repair_start_head_sha": reviewed_sha,
            "task_identity_sha256": task_digest,
            "review_result_sha256": result_digest,
        }
        selected = select_repair(
            {"repo": repo, "pr": pr, "branch": branch, "triage": triage},
            enabled=True, triage_ran=True, budget=2, state_dir=tmp_path,
        )
        assert verdict["route"] == selected["route"] == "repair"
        assert selected["task"] == task and selected["findings"] == findings
        assert selected["repair_start_head_sha"] == reviewed_sha

        intent = __import__("lokay.proc.pr_repair_receipts", fromlist=["build_push_intent"]).build_push_intent(
            repo=repo, pr=pr, branch=branch, repair_kind="review",
            start_head_sha=reviewed_sha, target_head_sha=pushed_sha,
            reviewed_head_sha=reviewed_sha, task=task, findings=findings,
            task_identity_sha256=task_digest, review_result_sha256=result_digest,
        )
        receipts = __import__("lokay.proc.pr_repair_receipts", fromlist=["prepare_push_intent"])
        assert receipts.prepare_push_intent(
            repo=repo, pr=pr, intent=intent, budget=2, state_dir=tmp_path,
        )["route"] == "recorded"
        assert receipts.mark_push_attempted(
            repo=repo, pr=pr, intent_sha256=intent["intent_sha256"],
            state_dir=tmp_path,
        )["route"] == "ready"
        monkeypatch.setattr(
            "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair",
            lambda **_kwargs: {
                "ok": True, "repo": repo, "pr": pr, "branch": branch,
                "terminal": "publish", "repaired": True, "published": True,
                "head_sha": pushed_sha, "reviewed_head_sha": reviewed_sha,
                "task": task, "findings": findings,
                "task_identity_sha256": task_digest,
                "review_result_sha256": result_digest,
                "repair_push_intent_sha256": intent["intent_sha256"],
            },
        )
        monkeypatch.setattr(
            "lokay.proc.run_parent_pr_repair_subflow.pr_repair_push.reconcile_pending_push",
            lambda **_kwargs: receipts.confirm_pending_push(
                repo=repo, pr=pr, intent_sha256=intent["intent_sha256"],
                remote_head_sha=pushed_sha, remote_branch=branch,
                remote_repo=repo, remote_state="OPEN", budget=2,
                state_dir=tmp_path,
            ),
        )
        current_remote[0] = pushed_sha
        repaired = run_parent_repair(selected, config_path=None, live=True)
        assert repaired["route"] == "completed"
        assert repaired["attempts"] in {1, 2}

        comments.append(format_review_marker(
            head_sha=reviewed_sha, verdict="request_changes", merge_ok=False,
            result_sha256=result_digest, artifact_sha256="f" * 64,
        ))
        next_review = resolve_sha_review({"head_sha": pushed_sha, "comments": comments})
        assert next_review["route"] == "agent"
        current_head = pushed_sha

    assert current_head == sha3
    assert repaired["attempts"] == 2
    assert len(comments) == 2

    third_findings_decision = {
        "verdict": "request_changes", "secrets": False, "task": task,
        "findings": findings, "reviewed_head_sha": sha3,
        "task_identity_sha256": task_digest,
        "review_result_sha256": hashlib.sha256(sha3.encode()).hexdigest(),
    }
    exhausted = select_repair(
        {"repo": repo, "pr": pr, "branch": branch, "triage": {
            "repairable": True, "repair_kind": "review", "review": third_findings_decision,
            "task": task, "findings": findings, "reviewed_head_sha": sha3,
            "repair_start_head_sha": sha3, "task_identity_sha256": task_digest,
            "review_result_sha256": third_findings_decision["review_result_sha256"],
        }},
        enabled=True, triage_ran=True, budget=2, state_dir=tmp_path,
    )
    assert exhausted["route"] == "fail_closed"
    assert exhausted["reason"] == "pr_repair_budget_exhausted"

    approved = {
        "verdict": "approve", "findings": [], "reviewed_head_sha": sha3,
        "task": task, "task_identity_sha256": task_digest,
        "review_result_sha256": hashlib.sha256(b"approved-sha-three").hexdigest(),
    }
    assert route_review_repair({"decision": approved})["route"] == "not_applicable"
    assert resolve_sha_review({"head_sha": sha3, "comments": comments})["route"] == "agent"
    merge_route = select_triage_outcome(
        {"route": "checks_passed", "head_sha": sha3},
        {"route": "not_applicable"},
        {"skipped": False, "passed": True},
    )
    assert merge_route["route"] == "merge"
    merge_ok, escalated = decide_review_merge(
        PrReviewDecision(verdict="approve"), 2, max_request_changes=2,
    )
    assert merge_ok is True and escalated is False

    merges = []
    contract = SimpleNamespace(pr=SimpleNamespace(
        merge_commit=lambda number, *, expected_head_sha: merges.append((number, expected_head_sha)),
    ))
    cfg = Config(
        mode="live", merge_enabled=True,
        repos=[RepoConfig(name=repo, clone_path=tmp_path)],
    )
    monkeypatch.setattr(pr_merge, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(pr_merge, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(pr_merge, "runner", lambda: object())
    monkeypatch.setattr(pr_merge, "load_code", lambda *_args, **_kwargs: contract)

    assert pr_merge.main(["--repo", repo, "--pr", str(pr), "--live",
                          "--expected-head-sha", sha3]) == 0
    assert merges == [(pr, sha3)]
    assert resolve_sha_review({"head_sha": sha3, "comments": comments})["route"] == "agent"

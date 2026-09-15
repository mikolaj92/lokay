"""Repair push intent is durable before the publication side effect."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc import pr_repair_receipts as receipts
from lokay.runner import CommandResult


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""mode: live
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_request_changes_per_pr: 2
repos:
  - name: o/r
    clone_path: {tmp_path / 'clone'}
""",
        encoding="utf-8",
    )
    return path


def _review_handoff() -> tuple[dict, list[dict], str]:
    task = {
        "repo": "o/r", "type": "Issue", "state": "OPEN", "number": 42,
        "title": "task", "body": "acceptance",
        "url": "https://github.com/o/r/issues/42",
    }
    findings = [{
        "path": "src/a.py", "start_line": 1, "end_line": 1,
        "severity": "high", "category": "bug", "content": "defect",
    }]
    task_sha = hashlib.sha256(json.dumps(
        task, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return task, findings, task_sha


class _GitEvidenceRunner:
    def __init__(self, target: str, branch: str):
        self.target = target
        self.branch = branch

    def run(self, spec, *, live: bool):
        assert live is True
        args = spec.argv[1:]
        if args[:2] == ("rev-parse", "--verify"):
            stdout = f"{self.target}\n"
        elif args[:2] == ("symbolic-ref", "--quiet"):
            stdout = f"{self.branch}\n"
        elif args[:1] == ("status",):
            stdout = ""
        else:
            raise AssertionError(spec.argv)
        return CommandResult(spec=spec, executed=True, returncode=0, stdout=stdout)


def test_repair_push_intent_is_fsynced_and_marked_before_push(
    tmp_path: Path, monkeypatch
) -> None:
    from lokay.organ import publication
    from lokay.proc import push_branch

    repo, pr, branch = "o/r", 9, "ai/fix/9-x"
    start, target = "a" * 40, "b" * 40
    config = _config(tmp_path)
    task, findings, task_sha = _review_handoff()
    result_digest = "c" * 64
    observed: list[dict] = []

    def push(main, argv):
        assert main is push_branch.main
        receipt = receipts.read(repo, pr, state_dir=tmp_path)
        intent = receipt["pending_push"]
        assert intent["push_attempted"] is True
        assert intent["start_head_sha"] == start
        assert intent["target_head_sha"] == target
        assert intent["branch"] == branch
        observed.append(intent)
        return {"ok": True, "head_sha": target, "branch": branch}

    monkeypatch.setattr("lokay.proc.pr_repair_push.load_config", lambda _path: SimpleNamespace(
        max_request_changes_per_pr=2, state_path=tmp_path / "state.jsonl",
    ), raising=False)
    monkeypatch.setattr("lokay.proc.pr_repair_push.mutations_allowed", lambda **_kwargs: True, raising=False)
    monkeypatch.setattr("lokay.preflight.require_healthy", lambda *_args, **_kwargs: None)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    monkeypatch.setattr(
        "lokay.proc.pr_repair_push.make_runner",
        lambda _cfg: _GitEvidenceRunner(target, branch), raising=False,
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_push._git_value",
        lambda _runner, _worktree, *args: (
            (0, target, "") if args[0] == "rev-parse"
            else (0, branch, "") if args[0] == "symbolic-ref"
            else (0, "", "")
        ),
    )
    inputs = {
        "repo": repo, "pr": pr, "branch": branch, "live": True,
        "config_path": str(config), "head_sha": start,
        "repair_kind": "review", "reviewed_head_sha": start,
        "task": task, "findings": findings,
        "task_identity_sha256": task_sha,
        "review_result_sha256": result_digest,
    }
    upstream = {
        "worktree_add": {"worktree": str(worktree), "branch": branch},
        "commit_initial_repair": {"committed": True},
        "test_local": {"ok": True, "passed": True},
        "assert_real_diff": {"ok": True, "real": True},
        "finalize_repair_tests": {"ok": True, "route": "publish"},
    }
    ctx = {
        "cfg": ["--config", str(config)], "live": ["--live"],
        "repo": repo, "issue_number": None, "pr_number": pr,
        "repair_mode": True, "branch": branch, "run_atom_main": push,
    }

    out = publication.handle_publication("push", inputs, upstream, ctx)

    assert out["ok"] is True, out
    assert len(observed) == 1
    stored = receipts.read(repo, pr, state_dir=tmp_path)
    assert stored["attempts"] == 0
    assert stored["pending_push"]["intent_sha256"] == observed[0]["intent_sha256"]


def test_repair_push_is_not_attempted_when_intent_cannot_be_recorded(
    tmp_path: Path, monkeypatch
) -> None:
    from lokay.organ import publication

    config = _config(tmp_path)
    task, findings, task_sha = _review_handoff()
    push_calls: list[object] = []
    monkeypatch.setattr(
        "lokay.proc.pr_repair_push.load_config",
        lambda _path: SimpleNamespace(
            max_request_changes_per_pr=2, state_path=tmp_path / "state.jsonl",
        ),
        raising=False,
    )
    monkeypatch.setattr("lokay.proc.pr_repair_push.mutations_allowed", lambda **_kwargs: True, raising=False)
    monkeypatch.setattr("lokay.preflight.require_healthy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("lokay.proc.pr_repair_push.make_runner", lambda _cfg: object(), raising=False)
    monkeypatch.setattr(
        "lokay.proc.pr_repair_push._git_value",
        lambda *_args: (0, "b" * 40, "") if _args[2] == "rev-parse"
        else (0, "ai/fix/9-x", "") if _args[2] == "symbolic-ref"
        else (0, "", ""),
    )
    monkeypatch.setattr(
        "lokay.proc.pr_repair_receipts.prepare_push_intent",
        lambda **_kwargs: {"ok": True, "route": "fail_closed", "reason": "already_pending"},
    )

    out = publication.handle_publication(
        "push",
        {
            "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x", "live": True,
            "config_path": str(config), "head_sha": "a" * 40,
            "repair_kind": "review", "reviewed_head_sha": "a" * 40,
            "task": task, "findings": findings,
            "task_identity_sha256": task_sha,
            "review_result_sha256": "c" * 64,
        },
        {
            "worktree_add": {"worktree": str(tmp_path / "worktree"), "branch": "ai/fix/9-x"},
            "commit_initial_repair": {"committed": True},
            "test_local": {"ok": True, "passed": True},
            "assert_real_diff": {"ok": True, "real": True},
            "finalize_repair_tests": {"ok": True, "route": "publish"},
        },
        {
            "cfg": ["--config", str(config)], "live": ["--live"],
            "repo": "o/r", "issue_number": None, "pr_number": 9,
            "repair_mode": True, "branch": "ai/fix/9-x",
            "run_atom_main": lambda *_args: push_calls.append(_args) or {"ok": True},
        },
    )

    assert out["ok"] is False
    assert out["reason"] == "already_pending"
    assert push_calls == []

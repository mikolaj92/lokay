"""CI repair starts from the exact PR head whose checks triggered repair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.runner import CommandResult


class _SequentialRunner:
    def __init__(self, responses: list[tuple[int, str, str]]):
        self.responses = list(responses)
        self.calls = []

    def run(self, spec, *, live: bool):
        self.calls.append(spec)
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=self.responses[len(self.calls) - 1][0],
            stdout=self.responses[len(self.calls) - 1][1],
            stderr=self.responses[len(self.calls) - 1][2],
        )

    def run_checked(self, spec, *, live: bool):
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError("command failed")
        return result


def test_pr_checks_report_carries_the_current_full_head_sha():
    from lokay.gh_prs import pr_checks_report

    head = "a" * 40
    runner = _SequentialRunner([
        (0, json.dumps({"headRefOid": head}), ""),
        (1, "build failed", ""),
        (0, json.dumps({"headRefOid": head}), ""),
    ])

    report = pr_checks_report(runner, "o/r", 9, live=True)

    assert report["status"] == "failed"
    assert report["head_sha"] == head
    assert len(runner.calls) == 3


def test_pr_checks_report_does_not_promote_malformed_head_identity():
    from lokay.gh_prs import pr_checks_report

    runner = _SequentialRunner([
        (0, json.dumps({"headRefOid": "a" * 40}), ""),
        (1, "build failed", ""),
        (0, json.dumps({"headRefOid": "not-a-sha"}), ""),
    ])

    report = pr_checks_report(runner, "o/r", 9, live=True)

    assert report["status"] == "failed"
    assert report["head_sha"] == ""


def test_pr_checks_report_head_drift_is_not_repair_evidence():
    from lokay.gh_prs import pr_checks_report

    runner = _SequentialRunner([
        (0, json.dumps({"headRefOid": "a" * 40}), ""),
        (1, "build failed", ""),
        (0, json.dumps({"headRefOid": "b" * 40}), ""),
    ])

    report = pr_checks_report(runner, "o/r", 9, live=True)

    assert report["status"] == "failed"
    assert report["head_sha"] == ""


def test_exact_repair_worktree_is_checked_out_at_published_branch_sha(tmp_path):
    import subprocess
    from lokay.config import Config, RepoConfig
    from lokay.git_worktree import ensure_repair_worktree
    from lokay.runner import Runner

    def git(*args, cwd=None):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()

    bare = tmp_path / "origin.git"
    clone = tmp_path / "clone"
    source = tmp_path / "source"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    git("config", "user.name", "Repair Test", cwd=source)
    git("config", "user.email", "repair@example.test", cwd=source)
    (source / "file.txt").write_text("published\n")
    git("add", "file.txt", cwd=source)
    git("commit", "-qm", "published", cwd=source)
    git("branch", "-M", "ai/fix/9-task", cwd=source)
    git("remote", "add", "origin", str(bare), cwd=source)
    git("push", "-qu", "origin", "ai/fix/9-task", cwd=source)
    expected = git("rev-parse", "HEAD", cwd=source)
    subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True)
    worktrees = tmp_path / "worktrees"
    cfg = Config(worktrees_root=worktrees)
    repo = RepoConfig(name="o/r", clone_path=clone)

    import lokay.git_worktree as git_worktree
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        git_worktree, "_repair_head_repository_url", lambda _repo: str(bare), raising=False,
    )
    worktree = ensure_repair_worktree(
        Runner(), cfg, repo, "ai/fix/9-task", expected,
        head_repo="o/r", live=True,
    )

    assert git("rev-parse", "HEAD", cwd=worktree) == expected
    assert git("branch", "--show-current", cwd=worktree) == "ai/fix/9-task"
    assert not git("status", "--porcelain", cwd=worktree)
    monkeypatch.undo()


def test_exact_repair_worktree_rejects_remote_sha_drift_without_creating_worktree(tmp_path):
    import subprocess
    from lokay.config import Config, RepoConfig
    from lokay.git_worktree import ensure_repair_worktree
    from lokay.runner import Runner

    bare = tmp_path / "origin.git"
    clone = tmp_path / "clone"
    source = tmp_path / "source"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Repair Test"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "repair@example.test"], check=True)
    (source / "file.txt").write_text("published\n")
    subprocess.run(["git", "-C", str(source), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "published"], check=True)
    subprocess.run(["git", "-C", str(source), "branch", "-M", "ai/fix/9-task"], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin", str(bare)], check=True)
    subprocess.run(["git", "-C", str(source), "push", "-qu", "origin", "ai/fix/9-task"], check=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True)
    worktrees = tmp_path / "worktrees"

    import lokay.git_worktree as git_worktree
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        git_worktree, "_repair_head_repository_url", lambda _repo: str(bare), raising=False,
    )
    with pytest.raises(RuntimeError, match="does not match recorded repair SHA"):
        ensure_repair_worktree(
            Runner(), Config(worktrees_root=worktrees),
            RepoConfig(name="o/r", clone_path=clone), "ai/fix/9-task",
            "f" * 40, head_repo="o/r", live=True,
        )
    monkeypatch.undo()

    assert not (worktrees / "o__r" / "ai__fix__9-task").exists()


def test_repair_start_preflight_rejects_fork_hosted_branch(monkeypatch, tmp_path):
    from lokay.proc import worktree_add

    expected = "f" * 40
    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: {
            "headRefOid": expected,
            "headRepository": {"nameWithOwner": "contributor/r"},
        },
    )

    result = worktree_add.verify_repair_start_identity(
        _SequentialRunner([]), repo="o/r", pr=9, worktree=tmp_path,
        expected_head_sha=expected,
    )

    assert result["route"] == "missing"
    assert result["reason"] == "fork_hosted_repair_unsupported"


def test_repair_start_preflight_requires_remote_and_worktree_to_match_sha(monkeypatch, tmp_path):
    from lokay.proc import worktree_add

    expected = "f" * 40
    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: {
            "headRefOid": expected,
            "headRepository": {"nameWithOwner": "o/r"},
        },
    )
    runner = _SequentialRunner([
        (0, expected + "\n", ""),
        (0, "", ""),
    ])

    result = worktree_add.verify_repair_start_identity(
        runner, repo="o/r", pr=9, worktree=tmp_path, expected_head_sha=expected,
    )

    assert result["route"] == "ready"
    assert result["repair_start_head_sha"] == expected
    assert len(runner.calls) == 2


def test_repair_start_preflight_rejects_remote_drift(monkeypatch, tmp_path):
    from lokay.proc import worktree_add

    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: {
            "headRefOid": "e" * 40,
            "headRepository": {"nameWithOwner": "o/r"},
        },
    )
    runner = _SequentialRunner([(0, "f" * 40 + "\n", "")])

    result = worktree_add.verify_repair_start_identity(
        runner, repo="o/r", pr=9, worktree=tmp_path, expected_head_sha="f" * 40,
    )

    assert result["route"] == "missing"
    assert result["reason"] == "repair_start_head_mismatch"


def test_repair_start_preflight_continues_a_descendant_of_the_recorded_sha(monkeypatch, tmp_path):
    """An unpushed repair commit stays on the same repair.

    The remote tip must still be the recorded SHA. Only the local HEAD may move
    forward, and only when git says it contains the recorded SHA.
    """
    from lokay.proc import worktree_add

    recorded = "c" * 40
    continued = "d" * 40
    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: {
            "headRefOid": recorded,
            "headRepository": {"nameWithOwner": "o/r"},
        },
    )
    runner = _SequentialRunner([
        (0, continued + "\n", ""),
        (0, "", ""),
        (0, "", ""),
    ])

    result = worktree_add.verify_repair_start_identity(
        runner, repo="o/r", pr=57, worktree=tmp_path, expected_head_sha=recorded,
    )

    assert result["route"] == "ready", result
    assert result["worktree_head_sha"] == continued
    assert result["repair_start_head_sha"] == recorded
    ancestry = runner.calls[1].argv
    assert list(ancestry[:5]) == ["git", "merge-base", "--is-ancestor", recorded, continued]


def test_repair_start_preflight_rejects_worktree_drift(monkeypatch, tmp_path):
    from lokay.proc import worktree_add

    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: {
            "headRefOid": "f" * 40,
            "headRepository": {"nameWithOwner": "o/r"},
        },
    )
    runner = _SequentialRunner([
        (0, "e" * 40 + "\n", ""),
        (1, "", ""),
        (0, "", ""),
    ])

    result = worktree_add.verify_repair_start_identity(
        runner, repo="o/r", pr=9, worktree=tmp_path, expected_head_sha="f" * 40,
    )

    assert result["route"] == "missing"
    assert result["reason"] == "repair_start_head_mismatch"


def test_repair_start_preflight_rejects_missing_expected_sha(monkeypatch, tmp_path):
    from lokay.proc import worktree_add

    monkeypatch.setattr(
        "lokay.gh_prs.gh_json",
        lambda *_args, **_kwargs: pytest.fail("must not inspect an unbound PR"),
    )
    runner = _SequentialRunner([])

    result = worktree_add.verify_repair_start_identity(
        runner, repo="o/r", pr=9, worktree=tmp_path, expected_head_sha="missing",
    )

    assert result["route"] == "missing"
    assert result["reason"] == "repair_start_head_missing"
    assert runner.calls == []


def test_repair_worktree_atom_passes_pr_and_exact_start_sha(monkeypatch):
    from lokay.organ.implement import handle_implement

    expected = "d" * 40
    calls = []

    def run_atom(_main, argv):
        calls.append(argv)
        return {"ok": True, "route": "ready"}

    result = handle_implement(
        "worktree_add",
        {"branch": "ai/fix/9-task", "pr": 9, "head_sha": expected},
        {},
        {"cfg": [], "live": [], "repo": "o/r", "issue_number": None,
         "pr_number": 9, "repair_mode": True, "branch": "ai/fix/9-task", "run_atom_main": run_atom},
    )

    assert result["route"] == "ready"
    assert calls and "--pr" in calls[0] and "9" in calls[0]
    assert "--repair-start-head-sha" in calls[0]
    assert expected in calls[0]


def test_ci_head_sha_flows_from_checks_through_factory_repair_selection(tmp_path: Path):
    from lokay.proc.classify_pr_triage_checks import classify
    from lokay.proc.select_pr_repair_department import select as select_repair
    from lokay.proc.select_pr_triage_outcome import select as select_outcome
    from lokay.proc.select_pr_triage_verdict import select as select_verdict
    from lokay.proc.summarize_pr_triage_department import summarize as summarize_department

    head = "b" * 40
    checks = classify({"status": "failed", "require_checks": True, "head_sha": head})
    assert checks["route"] == "repair"
    assert checks["head_sha"] == head

    outcome = select_outcome(checks, {}, {"skipped": True})
    assert outcome["repair_kind"] == "ci"
    assert outcome["head_sha"] == head

    triage_run = {
        "ok": True,
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-task",
        "triage": {
            "repairable": True,
            "repair_kind": "ci",
            "head_sha": head,
            "review": {"verdict": "not_applicable"},
        },
    }
    picked = {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-task"}
    verdict = select_verdict(picked, triage_run, {"route": "review"})
    receipt = summarize_department(picked, triage_run, verdict, {"route": "review"})

    selected = select_repair(
        receipt, enabled=True, triage_ran=True, state_dir=tmp_path,
    )
    assert selected["route"] == "repair"
    assert selected["repair_kind"] == "ci"
    assert selected["repair_start_head_sha"] == head


def test_failed_checks_without_stable_head_wait_instead_of_repairing():
    from lokay.proc.classify_pr_triage_checks import classify

    out = classify({"status": "failed", "require_checks": True, "head_sha": ""})

    assert out["route"] == "wait"
    assert out["waiting"] is True
    assert out["repairable"] is False
    assert out["reason"] == "ci_repair_start_head_missing"


def test_ci_repair_verdict_and_triage_terminal_preserve_checks_head_sha():
    from lokay.organ.pr_outcome import handle_pr_outcome
    from lokay.proc.summarize_pr_triage import summarize

    head = "e" * 40
    verdict = handle_pr_outcome(
        "pr_repair_verdict", {},
        {
            "select_pr_triage_outcome": {
                "route": "repair", "repair_kind": "ci", "head_sha": head,
                "reason": "checks_failed",
            },
            "publish_pr_review": {"decision": {"verdict": "not_applicable"}},
        },
        {"repo": "o/r", "pr_number": 9, "branch": "ai/fix/9-x", "live": False},
    )
    assert verdict["head_sha"] == head

    terminal = summarize(
        review={"decision": {"verdict": "not_applicable"}},
        repair={}, repair_manual={}, manual={}, merge={}, close={},
        outcome=verdict,
    )
    assert terminal["result"]["head_sha"] == head
    assert terminal["result"]["repair_kind"] == "ci"


def test_test_failure_ci_repair_retains_checks_head_sha():
    from lokay.proc.classify_pr_triage_checks import classify
    from lokay.proc.select_pr_triage_outcome import select

    head = "c" * 40
    checks = classify({"status": "passed", "head_sha": head})

    out = select(checks, {}, {"skipped": False, "passed": False})

    assert out["route"] == "repair"
    assert out["repair_kind"] == "ci"
    assert out["head_sha"] == head


def test_child_repair_kind_and_ci_start_head_reach_terminal_summary(monkeypatch):
    from lokay.organ import repair_boundary

    seen = {}

    def summarize(**kwargs):
        seen.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(repair_boundary, "load_config", lambda _path: object())
    monkeypatch.setattr("lokay.proc.summarize_pr_repair.summarize", summarize)
    repair_boundary.handle_repair_boundary(
        "summarize_pr_repair",
        {"repair_kind": "ci", "head_sha": "d" * 40, "branch": "ai/fix/9-task"},
        {"finalize_repair_tests": {"route": "not-publish"}, "push": {}},
        {"repo": "o/r", "pr_number": 9},
    )

    assert seen["repair_handoff"]["kind"] == "ci"
    assert seen["repair_handoff"]["start_head_sha"] == "d" * 40

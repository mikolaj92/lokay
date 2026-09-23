"""Final merge compare-and-swap, through the real organ/CLI/GitHub boundary."""
from __future__ import annotations

import json
import subprocess

import pytest

from lokay.atom_runtime import run_atom_main
from lokay.code import github
from lokay.config import Config
from lokay.organ.lanes import handle_lanes
from lokay.proc import pr_merge
from lokay.runner import CommandResult

A = "a" * 40
B = "b" * 40


@pytest.mark.parametrize("remote_head", [A, B])
def test_final_merge_is_bound_to_review_and_local_test(monkeypatch, remote_head):
    cfg = Config(merge_enabled=True, merge_mode="always", require_llm_review=True)
    monkeypatch.setattr("lokay.config.load_config", lambda *_: cfg)
    monkeypatch.setattr(pr_merge, "load_cfg", lambda *_: cfg)
    monkeypatch.setattr(pr_merge, "mutations_allowed", lambda **_: True)
    calls = []
    merged = []

    class Remote:
        def run_checked(self, spec, *, live):
            calls.append(spec.argv)
            # Simulate the server's atomic comparison, not a pre-merge probe.
            expected = (spec.argv[spec.argv.index("--match-head-commit") + 1]
                        if "--match-head-commit" in spec.argv else None)
            if expected is not None and expected != remote_head:
                raise RuntimeError("Head commit of pull request changed")
            merged.append(remote_head)
            return CommandResult(spec=spec, executed=live, returncode=0)

    monkeypatch.setattr(pr_merge, "runner", Remote)
    monkeypatch.setattr(github, "view_pr", lambda *_a, **_k: {})
    up = {
        "pr_checks": {"ok": True, "status": "passed", "green": True, "head_sha": A},
        "publish_pr_review": {"ok": True, "merge_ok": True, "head_sha": A,
                              "decision": {"verdict": "approve", "reviewed_head_sha": A}},
        "test_local": {"ok": True, "tested": True, "tested_head_sha": A},
    }
    out = handle_lanes("pr_merge", {}, up, {
        "cfg": [], "live": ["--live"], "repo": "owner/repo", "pr_number": 7,
        "issue_number": None, "branch": "ai/fix/7", "run_atom_main": run_atom_main,
    })
    assert calls[0] == ("gh", "pr", "merge", "7", "--repo", "owner/repo", "--merge",
                        "--delete-branch=false", "--match-head-commit", A)
    if remote_head == A:
        assert out["merged"] is True
        assert merged == [A]
    else:
        assert not out.get("merged")
        assert merged == []
        from lokay.proc.summarize_pr_triage import summarize
        from lokay.proc.walk_pr_leftover import consumes
        summary = summarize(review=up["publish_pr_review"], repair={}, repair_manual={},
                            manual={}, merge=out, close={}, outcome={"route": "merge"})["result"]
        assert summary["waiting"] is True
        assert not consumes(summary)
        # Approval of A cannot authorize B on the next pass.
        from lokay.proc.resolve_sha_review import resolve
        from lokay.pr_review import format_review_marker
        marker = format_review_marker(head_sha=A, verdict="approve", merge_ok=True)
        assert resolve({"head_sha": B, "comments": [marker]})["route"] == "agent"


def test_pr_merge_off_mode_never_merges(monkeypatch):
    """A named off mode blocks a green, approved PR."""
    from lokay.atom_runtime import run_atom_main
    from lokay.config import Config
    from lokay.organ.lanes import handle_lanes

    monkeypatch.setattr("lokay.config.load_config", lambda *_: Config(merge_mode="off"))
    out = handle_lanes(
        "pr_merge", {},
        {"pr_checks": {"status": "passed", "merge_ok": True},
         "publish_pr_review": {"merge_ok": True,
                               "decision": {"verdict": "approve", "risk": "low"}}},
        {"cfg": [], "live": [], "repo": "o/r", "pr_number": 1, "issue_number": None,
         "branch": "ai/fix/1", "run_atom_main": run_atom_main},
    )
    assert out["skipped"] is True and out["reason"] == "merge_disabled"
    assert out.get("merged") is not True


@pytest.mark.parametrize("reviewed,tested", [(None, A), (A, None), (A, B), ("main", A), ("", "")])
def test_merge_refuses_unbound_evidence(monkeypatch, reviewed, tested):
    monkeypatch.setattr("lokay.config.load_config", lambda *_: Config(merge_enabled=True))
    calls = []
    out = handle_lanes("pr_merge", {}, {
        "pr_checks": {"ok": True, "status": "passed", "green": True},
        "publish_pr_review": {"ok": True, "merge_ok": True,
                              "decision": {"verdict": "approve", "reviewed_head_sha": reviewed}},
        "test_local": {"ok": True, "tested_head_sha": tested},
    }, {"cfg": [], "live": ["--live"], "repo": "owner/repo", "pr_number": 7,
        "issue_number": None, "branch": "ai/fix/7",
        "run_atom_main": lambda *args: calls.append(args) or {"ok": True, "merged": True}})
    assert calls == []
    assert not out.get("merged")


@pytest.mark.parametrize("sha", [None, "", "main", "a" * 7])
def test_cli_missing_sha_never_reaches_adapter(monkeypatch, capsys, sha):
    monkeypatch.setattr(pr_merge, "load_cfg", lambda *_: Config(merge_enabled=True))
    monkeypatch.setattr(pr_merge, "mutations_allowed", lambda **_: True)
    calls = []
    monkeypatch.setattr(pr_merge, "load_code", lambda *a, **k: calls.append(a))
    argv = ["--repo", "owner/repo", "--pr", "7", "--live"]
    if sha is not None:
        argv.extend(["--expected-head-sha", sha])
    pr_merge.main(argv)
    assert calls == []
    assert json.loads(capsys.readouterr().out)["ok"] is False


@pytest.mark.parametrize("mutation", ["none", "host_evidence", "commit", "dirty", "initial_dirty", "initial_drift"])
@pytest.mark.parametrize("test_result", [
    {"ok": True, "tested": True},
    {"ok": True, "tested": True, "cached": True},
    {"ok": True, "skipped": True, "reason": "no_declared_test"},
])
def test_local_test_attests_only_unchanged_clean_head(tmp_path, monkeypatch, mutation, test_result):
    from lokay import fala_organ

    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-q")
    git("config", "user.email", "test@example.test")
    git("config", "user.name", "Test")
    (tmp_path / "code.py").write_text("before\n")
    git("add", ".")
    git("commit", "-qm", "before")
    head = git("rev-parse", "HEAD")
    if mutation == "host_evidence":
        (tmp_path / ".lokay").mkdir()
        (tmp_path / ".lokay/approach.md").write_text("host approach\n")
        (tmp_path / ".lokay/localize.json").write_text("{}\n")

    if mutation.startswith("initial_"):
        (tmp_path / "code.py").write_text("changed before tests\n")
        if mutation == "initial_drift":
            git("commit", "-qam", "drift")

    def tests(**kwargs):
        assert not mutation.startswith("initial_"), "must refuse before executing tests"
        if mutation not in {"none", "host_evidence"}:
            (tmp_path / "code.py").write_text("after\n")
            if mutation == "commit":
                git("commit", "-qam", "after")
        return {**test_result, "worktree": str(tmp_path)}

    monkeypatch.setattr("lokay.proc.test_local_execution_subflow.run", tests)
    out = fala_organ._handle("test_local", {"repo": "owner/repo", "pr": 7}, {
        "publish_pr_review": {"decision": {"verdict": "approve", "reviewed_head_sha": head}},
        "worktree_add": {"ok": True, "worktree": str(tmp_path)},
    })
    if mutation in {"none", "host_evidence"}:
        assert out["tested_head_sha"] == head
    else:
        assert not out.get("tested_head_sha")
        assert out["ok"] is False

"""#1069: verify repair conducts; dirty Done-means committed; observation ignores skipped repair."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lokay.git_commit import commit_all
from lokay.organ.acceptance_boundary import handle_acceptance
from lokay.proc.finalize_acceptance import finalize
from lokay.runner import Runner


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.hookspath=", "-C", str(repo), *args], text=True
    )


def test_finalize_acceptance_prefers_recheck_publish() -> None:
    out = finalize(
        {"accepted": False, "route": "repair", "failed_evidence": ["test"]},
        {"accepted": True, "route": "publish"},
        {"ok": True, "passed": True},
    )
    assert out == {
        "ok": True,
        "route": "publish",
        "accepted": True,
        "reason": "acceptance_recheck",
        "failed_evidence": [],
    }


def test_finalize_acceptance_repair_terminal_ok_true() -> None:
    out = finalize(
        {"accepted": False, "route": "repair", "failed_evidence": ["test"]},
        {"accepted": False, "route": "repair", "failed_evidence": ["test"]},
        {"ok": True, "passed": False},
    )
    assert out["ok"] is True
    assert out["route"] == "repair_terminal"
    assert out["accepted"] is False


def test_verify_acceptance_ok_true_on_repair(tmp_path: Path) -> None:
    from lokay.acceptance import prepare_acceptance

    issue = {"repo": "a/b", "number": 1, "title": "t", "body": "- [ ] x"}
    art = prepare_acceptance(
        issue,
        root=tmp_path,
        evidence=[{"kind": "test", "expect": "declared repository tests pass"}],
    )
    up = {
        "prepare_acceptance": art,
        "finalize_local_tests": {"route": "not_publish"},
        "select_local_test": {"route": "fail"},
        "test_local_execution": {"ok": False, "tested": True},
        "local_repair_execution": {"reason": "condition_not_met", "skipped": True},
    }
    out = handle_acceptance("verify_acceptance", {}, up, {})
    assert out is not None
    assert out["ok"] is True
    assert out["accepted"] is False
    assert out["route"] == "repair"


def test_verify_acceptance_uses_finalize_publish_not_skipped_repair(
    tmp_path: Path,
) -> None:
    from lokay.acceptance import prepare_acceptance

    issue = {"repo": "a/b", "number": 2, "title": "t", "body": "- [ ] x"}
    art = prepare_acceptance(
        issue,
        root=tmp_path,
        evidence=[{"kind": "test", "expect": "declared repository tests pass"}],
    )
    up = {
        "prepare_acceptance": art,
        "finalize_local_tests": {"route": "publish"},
        "select_local_test": {"route": "pass"},
        "test_local_execution": {"ok": True, "tested": True, "passed": True},
        "local_repair_execution": {"reason": "condition_not_met"},
    }
    out = handle_acceptance("verify_acceptance", {}, up, {})
    assert out is not None
    assert out["ok"] is True
    assert out["accepted"] is True
    assert out["route"] == "publish"


def test_commit_all_includes_dirty_done_means_outside_localize(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "mojo").mkdir()
    (repo / "mojo" / "cli.mojo").write_text("old\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    (repo / "src" / "app.py").write_text("on goal\n", encoding="utf-8")
    (repo / "mojo" / "cli.mojo").write_text("done means\n", encoding="utf-8")
    evidence = repo / ".lokay"
    evidence.mkdir()
    (evidence / "localize.json").write_text(
        json.dumps({"paths": ["src/app.py"]}),
        encoding="utf-8",
    )
    assert commit_all(Runner(), repo, "done means", live=True) is True
    names = _git(repo, "show", "--pretty=format:", "--name-only", "HEAD").splitlines()
    assert "src/app.py" in names
    assert "mojo/cli.mojo" in names

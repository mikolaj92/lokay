"""Plan/localize-only diffs are not progress and cannot pr_create."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lokay import fala_organ
from lokay.git_real_diff import classify_changed_paths
from lokay.graph_run import describe_package
from lokay.proc import assert_real_diff


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(root: Path) -> Path:
    _git(root.parent, "init", "-b", "main", str(root))
    _git(root, "config", "user.email", "lokay@test")
    _git(root, "config", "user.name", "lokay-test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_classify_plan_only_lockstep():
    assert classify_changed_paths([".lokay/approach.md", ".lokay/localize.json"]) == "plan_only"
    assert classify_changed_paths([".lokay/approach.md"]) == "plan_only"
    assert classify_changed_paths(["./.lokay/localize.json"]) == "plan_only"
    assert classify_changed_paths([]) == "empty"
    assert classify_changed_paths(["src/lokay/proc/host_ff.py"]) == "real"
    assert classify_changed_paths(["src/x.py", ".lokay/approach.md"]) == "real"


def test_worktree_only_approach_and_localize_is_not_progress(tmp_path: Path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "ai/fix/1-x")
    lokay = repo / ".lokay"
    lokay.mkdir()
    (lokay / "approach.md").write_text("# Approach plan\n", encoding="utf-8")
    (lokay / "localize.json").write_text('{"paths":[]}\n', encoding="utf-8")
    _git(repo, "add", "-f", "--", ".lokay/approach.md", ".lokay/localize.json")
    _git(repo, "commit", "-m", "plan only")

    code = assert_real_diff.main(["--worktree", str(repo), "--base", "main"])
    payload = _payload(capsys)
    assert code == 1
    assert payload["ok"] is False
    assert payload["reason"] == "plan_only"
    assert payload["real"] is False


def test_worktree_with_unix_atom_is_real_progress(tmp_path: Path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "ai/fix/1-x")
    lokay = repo / ".lokay"
    lokay.mkdir()
    (lokay / "approach.md").write_text("# Approach plan\n", encoding="utf-8")
    (lokay / "localize.json").write_text('{"paths":["src/app.py"]}\n', encoding="utf-8")
    (repo / "src" / "app.py").write_text("print('fixed')\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "add", "-f", "--", ".lokay/approach.md", ".lokay/localize.json")
    _git(repo, "commit", "-m", "real fix")

    code = assert_real_diff.main(["--worktree", str(repo), "--base", "main"])
    payload = _payload(capsys)
    assert code == 0
    assert payload["ok"] is True
    assert payload["real"] is True
    assert "src/app.py" in payload["paths"]


def test_worktree_with_source_outside_localize_is_off_goal(tmp_path: Path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-b", "ai/fix/1-x")
    lokay = repo / ".lokay"
    lokay.mkdir()
    (lokay / "localize.json").write_text('{"paths":["src/app.py"]}\n', encoding="utf-8")
    (repo / "src" / "other.py").write_text("print('off goal')\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "add", "-f", "--", ".lokay/localize.json")
    _git(repo, "commit", "-m", "off-goal source")

    code = assert_real_diff.main(["--worktree", str(repo), "--base", "main"])
    payload = _payload(capsys)
    assert code == 1
    assert payload["ok"] is False
    assert payload["reason"] == "off_goal"
    assert payload["real"] is False
    assert payload["off_goal_paths"] == ["src/other.py"]


def test_empty_diff_is_not_progress(tmp_path: Path, capsys):
    repo = _init_repo(tmp_path / "repo")
    code = assert_real_diff.main(["--worktree", str(repo), "--base", "main"])
    payload = _payload(capsys)
    assert code == 1
    assert payload["reason"] == "zero_diff"


def _ok_real_diff() -> dict:
    return {"ok": True, "real": True, "kind": "real"}


def _plan_only() -> dict:
    return {
        "ok": False,
        "reason": "plan_only",
        "error": "refusing: diff is only plan/localize evidence",
    }


def test_organ_plan_only_never_reaches_pr_create(monkeypatch):
    def boom(main, argv):
        raise AssertionError("gh pr create must not run for a plan-only diff")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "pr_create",
        {"repo": "a/b", "live": False},
        {
            "get_issue": {
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "title": "Fix thing",
                    "body": "",
                    "labels": [],
                    "assignees": [],
                    "url": "https://example.test/7",
                }
            },
            "make_branch": {"branch": "ai/fix/7-x"},
            "run_agent": {"ok": True},
            "test_local": {"ok": True, "tested": True, "skipped": False},
            "assert_real_diff": _plan_only(),
            "push": {"ok": True},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "plan_only"


def test_organ_plan_only_never_pushes(monkeypatch):
    def boom(main, argv):
        raise AssertionError("push must not run for a plan-only diff")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": {"ok": True, "tested": True, "skipped": False},
            "assert_real_diff": _plan_only(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "plan_only"


def test_organ_push_without_real_diff_fails(monkeypatch):
    def boom(main, argv):
        raise AssertionError("push must not run without assert_real_diff")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": {"ok": True, "tested": True, "skipped": False},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "real_diff_missing"
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    by_id = {n["id"]: n for n in path["nodes"]}
    assert "assert_real_diff" in by_id
    assert "assert_real_diff" in by_id["push"]["conduction"]
    assert "assert_real_diff" in by_id["pr_create"]["conduction"]
    assert "run_agent" in by_id["assert_real_diff"]["conduction"]
    # commit_all must not wait on assert_real_diff (that cycle never reaches push).
    assert "assert_real_diff" not in by_id["commit_all"]["conduction"]
    assert "push" not in by_id["assert_real_diff"]["conduction"]
    assert "pr_create" not in by_id["assert_real_diff"]["conduction"]

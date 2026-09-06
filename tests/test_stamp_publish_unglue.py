"""Done-means stamps: auto-commit + fail-closed; publish gate unglued from verify."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lokay.git_commit import commit_all
from lokay.proc.assert_stamps_committed import assert_clean
from lokay.proc.list_dirty_stamp_paths import list_paths
from lokay.proc.select_publish_gate import select
from lokay.runner import Runner


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-c", "core.hookspath=", "-C", str(repo), *args], text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("base\n", encoding="utf-8")
    (repo / "README.md").write_text("Version 0.1.0\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")


def test_commit_all_includes_dirty_stamp_outside_localize(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src" / "app.py").write_text("on goal\n", encoding="utf-8")
    (repo / "README.md").write_text("Version 0.2.0\n", encoding="utf-8")
    evidence = repo / ".lokay"
    evidence.mkdir()
    (evidence / "localize.json").write_text(
        json.dumps({"paths": ["src/app.py"]}),
        encoding="utf-8",
    )
    assert commit_all(Runner(), repo, "on goal + stamps", live=True) is True
    names = _git(repo, "show", "--pretty=format:", "--name-only", "HEAD").splitlines()
    assert "src/app.py" in names
    assert "README.md" in names
    status = _git(repo, "status", "--porcelain")
    assert "README.md" not in status and "src/app.py" not in status
    assert "?? .lokay/" in status


def test_assert_stamps_committed_fail_closed_on_dirty_readme(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("Version 9.9.9\n", encoding="utf-8")
    listed = list_paths(repo, live=True)
    assert listed["route"] == "dirty"
    assert "README.md" in listed["dirty_stamps"]
    verdict = assert_clean(listed)
    assert verdict["ok"] is False
    assert verdict["reason"] == "dirty_stamp_files"


def test_select_publish_gate_names_failed_atom() -> None:
    blocked = select(
        finalize_local_tests={"route": "publish"},
        finalize_acceptance={"accepted": True, "route": "publish"},
        assert_stamps_committed={"ok": False, "route": "fail", "dirty_stamps": ["README.md"]},
    )
    assert blocked["route"] == "block"
    assert blocked["failed_atom"] == "assert_stamps_committed"
    opened = select(
        finalize_local_tests={"route": "publish"},
        finalize_acceptance={"accepted": True, "route": "publish"},
        assert_stamps_committed={"ok": True, "route": "publish"},
    )
    assert opened == {"ok": True, "route": "publish", "reason": "publish_gate_open"}

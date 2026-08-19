from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lokay.git_commit import commit_all
from lokay.runner import Runner


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")


def test_commit_all_refuses_configured_checkout_on_main(tmp_path: Path) -> None:
    repo = tmp_path / "mill-checkout"
    _init_repo(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    before = _git(repo, "rev-parse", "HEAD").strip()
    tracked.write_text("dirty\n", encoding="utf-8")

    assert commit_all(
        Runner(),
        repo,
        "must not land on main",
        live=True,
        protected_checkouts=[repo],
    ) is False

    assert _git(repo, "rev-parse", "HEAD").strip() == before
    assert _git(repo, "status", "--short").splitlines() == [" M tracked.txt"]


def test_commit_all_commits_only_localized_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    source = repo / "src" / "app.py"
    foreign = repo / "src" / "lokay" / "proc" / "factory_begin.py"
    source.parent.mkdir(parents=True)
    foreign.parent.mkdir(parents=True)
    source.write_text("base\n", encoding="utf-8")
    foreign.write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")

    source.write_text("on goal\n", encoding="utf-8")
    foreign.write_text("off goal\n", encoding="utf-8")
    evidence = repo / ".lokay"
    evidence.mkdir()
    (evidence / "approach.md").write_text("# Approach\n", encoding="utf-8")
    (evidence / "localize.json").write_text(
        json.dumps({"paths": ["src/app.py", "tests/test_app.py"]}),
        encoding="utf-8",
    )

    assert commit_all(Runner(), repo, "on goal", live=True) is True

    assert _git(repo, "show", "--pretty=format:", "--name-only", "HEAD").splitlines() == [
        "src/app.py"
    ]
    assert _git(repo, "status", "--short").splitlines() == [
        " M src/lokay/proc/factory_begin.py",
        "?? .lokay/",
    ]

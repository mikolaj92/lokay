"""Physical path attribution with a moving upstream and real Git repositories."""

import subprocess

from lokay.git_real_diff import list_changed_paths
from lokay.runner import Runner


def test_changed_paths_exclude_upstream_only_changes(tmp_path):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "Diff Test")
    git("config", "user.email", "diff@example.invalid")
    (tmp_path / "existing.py").write_text("original\n")
    git("add", ".")
    git("commit", "-m", "base")
    git("branch", "work")
    (tmp_path / "upstream.py").write_text("upstream only\n")
    git("add", ".")
    git("commit", "-m", "upstream advances")
    git("checkout", "work")

    # An old, otherwise untouched worktree must not look productive/off-goal.
    assert list_changed_paths(Runner(), tmp_path, base="main") == []

    (tmp_path / "committed.py").write_text("worker commit\n")
    git("add", ".")
    git("commit", "-m", "worker change")
    (tmp_path / "staged.py").write_text("staged\n")
    git("add", "staged.py")
    (tmp_path / "existing.py").write_text("unstaged\n")
    (tmp_path / "untracked.py").write_text("untracked\n")
    assert list_changed_paths(Runner(), tmp_path, base="main") == [
        "committed.py", "existing.py", "staged.py", "untracked.py"
    ]

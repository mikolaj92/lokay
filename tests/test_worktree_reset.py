"""worktree --reset-base flag wiring (no live git)."""

from types import SimpleNamespace

import pytest

from lokay.config import Config, RepoConfig
from lokay.git_worktree import InvalidBranchRef, assert_valid_branch_ref, ensure_worktree
from lokay.proc import worktree_add
from lokay.runner import Runner


def test_worktree_add_reset_base_dry(tmp_path, monkeypatch):
    # Without --live, ensure_worktree returns planned path and does not touch git.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
  - name: owner/repo
    clone_path: {tmp_path / "clone"}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    code = worktree_add.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "owner/repo",
            "--branch",
            "ai/fix/1-x",
            "--reset-base",
        ]
    )
    assert code == 0


def test_assert_valid_branch_ref_rejects_dotdot():
    with pytest.raises(InvalidBranchRef) as caught:
        assert_valid_branch_ref(Runner(), "ai/fix/7-foo-..-bar")
    assert caught.value.reason == "invalid_branch_ref"


def _result(argv, *, returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        spec=SimpleNamespace(argv=tuple(argv)),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class _ResetRunner:
    """Records git argv; answers check-ref-format + rev-list --count."""

    def __init__(self, *, ahead: str | None = "0", ahead_rc: int = 0) -> None:
        self.ahead = ahead
        self.ahead_rc = ahead_rc
        self.calls: list[list[str]] = []

    def run(self, spec, *, live):
        argv = list(spec.argv)
        self.calls.append(argv)
        if argv[1:3] == ["check-ref-format", "--normalize"]:
            return _result(argv)
        if argv[1:4] == ["rev-list", "--count", "origin/main..HEAD"]:
            return _result(argv, returncode=self.ahead_rc, stdout=(self.ahead or "") + "\n")
        return _result(argv)

    def run_checked(self, spec, *, live):
        result = self.run(spec, live=live)
        if result.returncode != 0:
            raise RuntimeError(f"command failed: {spec.argv}")
        return result


def _cfg_repo(tmp_path, branch: str):
    clone = tmp_path / "clone"
    clone.mkdir()
    worktrees = tmp_path / "wt"
    wt = worktrees / "owner__repo" / branch.replace("/", "__")
    wt.mkdir(parents=True)
    cfg = Config(worktrees_root=worktrees, repos=[])
    repo = RepoConfig(name="owner/repo", clone_path=clone)
    return cfg, repo, wt


def test_reset_to_base_keeps_worktree_when_ahead(tmp_path):
    branch = "ai/fix/164-observe"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    destructive = {"remove", "add", "push"}
    assert not any(call[1] in destructive for call in runner.calls)
    assert any(call[1:4] == ["rev-list", "--count", "origin/main..HEAD"] for call in runner.calls)


def test_reset_to_base_rewrites_when_ahead_zero(tmp_path):
    branch = "ai/fix/164-observe"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="0")
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    assert any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)
    assert any(call[1:3] == ["worktree", "add"] and "-B" in call for call in runner.calls)
    assert any(call[1:4] == ["push", "origin", "--delete"] for call in runner.calls)


def test_reset_to_base_fail_closed_when_ahead_unreadable(tmp_path):
    branch = "ai/fix/164-observe"
    cfg, repo, _wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="", ahead_rc=128)
    with pytest.raises(RuntimeError, match="ahead"):
        ensure_worktree(
            runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
        )
    assert not any(call[1] == "remove" for call in runner.calls)
    assert not any(call[1] == "add" for call in runner.calls)

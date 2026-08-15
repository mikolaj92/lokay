"""worktree --reset-base flag wiring (no live git)."""

import pytest

from lokay.git_worktree import InvalidBranchRef, assert_valid_branch_ref
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

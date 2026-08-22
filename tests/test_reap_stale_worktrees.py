"""reap_stale_worktrees: KEEP live / covering / dirty unpublished; REMOVE stale."""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lokay.passkit import io as pass_io
from lokay.proc import reap_stale_worktrees


def _ok() -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout="", stderr="")


@pytest.fixture(autouse=True)
def _open_issues_by_default(monkeypatch):
    # Most unit fixtures use a neutral repository name. Individual scope tests
    # restore the production mini-mill repository explicitly.
    monkeypatch.setattr(reap_stale_worktrees, "MINI_MILL_REPO", "owner/repo")
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", lambda repo, issue: False)


class _Git:
    def __init__(self) -> None:
        self.pushes: list[list[str]] = []

    def run(self, spec, *, live):
        argv = list(spec.argv)
        if argv[1:3] == ["fetch", "origin"]:
            if len(argv) > 3 and argv[3] != "main":
                raise AssertionError(f"per-branch fetch forbidden: {argv}")
            return _ok()
        if argv[1:4] == ["ls-remote", "--heads", "origin"]:
            return SimpleNamespace(
                returncode=0,
                stdout=getattr(self, "ls_remote", ""),
                stderr="",
            )
        if argv[1:3] == ["push", "origin"]:
            self.pushes.append(argv)
            return _ok()
        raise AssertionError(argv)


def _config(tmp_path: Path, *, repos: tuple[str, ...] = ("owner/repo",)) -> Path:
    path = tmp_path / "config.yaml"
    lines = []
    for name in repos:
        lines.append(f"  - name: {name}")
        lines.append(f"    clone_path: {tmp_path / 'clone'}")
    repo_block = "\n".join(lines)
    path.write_text(
        f"""
mode: live
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
{repo_block}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
worktrees:
  root: {tmp_path / 'wt'}
state:
  path: {tmp_path / 'state.jsonl'}
""",
        encoding="utf-8",
    )
    (tmp_path / "clone").mkdir(exist_ok=True)
    return path


def _pass(tmp_path: Path, *, working: dict[str, Any] | None = None) -> str:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"live": True, "repos": ["owner/repo"], "stuck_path": ""},
    )
    base = {
        "actions": [],
        "prs_by_repo": {},
        "merged_this_pass": [],
        "occupied_repos": [],
        "live_issue_to_pr_repos": [],
    }
    if working:
        base.update(working)
    pass_io.write_json(pass_io.working_path(pass_dir), base)
    return str(pass_dir)


def _corner(tmp_path: Path, branch: str = "ai/fix/142-prompt") -> Path:
    wt = tmp_path / "wt" / "owner__repo" / branch.replace("/", "__")
    wt.mkdir(parents=True)
    return wt


def test_keep_live_issue_to_pr(tmp_path, monkeypatch):
    branch = "ai/fix/54-bluesky"
    _corner(tmp_path, branch)
    monkeypatch.setattr(
        reap_stale_worktrees,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "owner/repo", "issue": 54, "pid": 61281}],
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify live")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    removed: list[str] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: removed.append("x") or {"ok": True, "removed": True},
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["ok"] is True
    assert out["reaped_count"] == 0
    assert out["kept_count"] == 1
    assert out["kept"][0]["reason"] == "live_issue_to_pr"
    assert removed == []
    assert (tmp_path / "wt" / "owner__repo" / "ai__fix__54-bluesky").is_dir()


def test_keep_other_branch_in_live_repo(tmp_path, monkeypatch):
    """K=1 live i2pr occupies the repo — do not reap a sibling leftover."""
    _corner(tmp_path, "ai/fix/142-old-tip")
    monkeypatch.setattr(
        reap_stale_worktrees,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "owner/repo", "issue": 54, "pid": 61281}],
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify live repo")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must KEEP live repo")),
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "live_issue_to_pr"
    assert out["reaped_count"] == 0


def test_keep_covering_open_pr(tmp_path, monkeypatch):
    branch = "ai/fix/54-bluesky"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify covering")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: {"ok": True, "removed": True},
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(
            tmp_path,
            working={
                "prs_by_repo": {
                    "owner/repo": [
                        {"number": 295, "head_ref": branch, "labels": ["ai:generated"]}
                    ]
                }
            },
        ),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "covering_pr"
    assert out["reaped_count"] == 0


def test_keep_unpublished_or_dirty(tmp_path, monkeypatch):
    branch = "ai/fix/54-x"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": True,
            "ahead": 2,
            "behind_main": 0,
            "published": False,
            "dirty": "empty",
            "keep_unpublished": True,
        },
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    removed: list[Path] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda runner, clone, path, **_kwargs: removed.append(path) or {"ok": True, "removed": True},
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "unpublished_or_dirty"
    assert removed == []


def test_keep_published_tip_with_real_uncommitted_work(tmp_path, monkeypatch):
    branch = "ai/fix/142-prompt-i-i-asked"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": True,
            "ahead": 3,
            "behind_main": 0,
            "published": True,
            "dirty": "real",
            "uncommitted": "real",
            "keep_unpublished": False,
        },
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must keep partial work")),
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )

    assert out["kept"][0]["reason"] == "uncommitted_real"
    assert out["reaped_count"] == 0


def test_keep_unpublished_behind_main_with_real_uncommitted_work(tmp_path, monkeypatch):
    branch = "ai/fix/142-prompt"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": True,
            "ahead": 3,
            "behind_main": 4,
            "published": False,
            "dirty": "real",
            "uncommitted": "real",
            "keep_unpublished": False,
        },
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must keep partial work")),
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )

    assert out["kept"][0]["reason"] == "uncommitted_real"
    assert out["reaped_count"] == 0


def test_remove_published_closed_tip(tmp_path, monkeypatch):
    branch = "ai/fix/142-prompt-i-i-asked"
    wt = _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": True,
            "ahead": 3,
            "behind_main": 0,
            "published": True,
            "dirty": "empty",
            "keep_unpublished": False,
        },
    )
    removed: list[Path] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda runner, clone, path, **_kwargs: removed.append(path) or {"ok": True, "removed": True},
    )
    git = _Git()
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: git)
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["reaped_count"] == 1
    assert out["reaped"][0]["reason"] == "stale"
    assert removed == [wt]
    assert git.pushes and git.pushes[0][1:4] == ["push", "origin", "--delete"]


def test_remove_unpublished_behind_main(tmp_path, monkeypatch):
    branch = "ai/fix/142-prompt"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": True,
            "ahead": 3,
            "behind_main": 4,
            "published": False,
            "dirty": "empty",
            "keep_unpublished": False,
        },
    )
    removed: list[Path] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda runner, clone, path, **_kwargs: removed.append(path) or {"ok": True, "removed": True},
    )

    class _NoDelete(_Git):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["push", "origin"]:
                raise AssertionError("must not delete unpublished remote")
            return super().run(spec, live=live)

    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _NoDelete())
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["reaped_count"] == 1
    assert len(removed) == 1


def test_keep_when_branch_fetch_unreadable(tmp_path, monkeypatch):
    branch = "ai/fix/54-x"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": False,
            "error": "cannot determine origin/ai/fix/54-x: unable to access",
        },
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must KEEP unreadability")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "unreadability"
    assert out["reaped_count"] == 0


def test_planned_does_not_remove(tmp_path, monkeypatch):
    _corner(tmp_path, "ai/fix/142-x")
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("planned must not remove")),
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=False,
    )
    assert out["planned"] is True
    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "planned"


def test_no_leftovers_skips_git(tmp_path, monkeypatch):
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])

    class _Boom:
        def run(self, spec, *, live):
            raise AssertionError(f"no leftovers: {spec.argv}")

    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Boom())
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["reaped_count"] == 0
    assert out["kept_count"] == 0


def test_keep_live_repo_from_working_json(tmp_path, monkeypatch):
    """Occupancy already wrote live_issue_to_pr_repos — do not wait for a live pid."""
    _corner(tmp_path, "ai/fix/51-list")
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify live repo")),
    )

    class _Boom:
        def run(self, spec, *, live):
            raise AssertionError(f"live repo must skip git: {spec.argv}")

    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Boom())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must KEEP live repo")),
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(
            tmp_path,
            working={"live_issue_to_pr_repos": ["owner/repo"]},
        ),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "live_issue_to_pr"
    assert out["reaped_count"] == 0


def test_ls_remote_failure_keeps_unreadability(tmp_path, monkeypatch):
    _corner(tmp_path, "ai/fix/142-x")
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify")),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must KEEP unreadability")),
    )

    class _NoHeads(_Git):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["ls-remote", "--heads", "origin"]:
                return SimpleNamespace(returncode=128, stdout="", stderr="unable to access")
            return super().run(spec, live=live)

    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _NoHeads())
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "unreadability"
    assert out["reaped_count"] == 0


def test_classify_uses_ls_remote_not_per_branch_fetch(tmp_path, monkeypatch):
    branch = "ai/fix/142-prompt"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    seen: list[bool] = []

    def _status(*a, **k):
        seen.append(bool(k.get("known_published")))
        return {
            "readable": True,
            "ahead": 3,
            "behind_main": 0,
            "published": True,
            "dirty": "empty",
            "keep_unpublished": False,
        }

    monkeypatch.setattr(reap_stale_worktrees, "leftover_status", _status)
    git = _Git()
    git.ls_remote = f"abc\trefs/heads/{branch}\n"
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: git)
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: {"ok": True, "removed": True},
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert seen == [True]
    assert out["reaped_count"] == 1


def test_keep_when_pr_survey_failed(tmp_path, monkeypatch):
    """Failed list_prs is unknown, not idle — do not delete a published tip."""
    branch = "ai/fix/40-show-hn"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify survey-failed repo")),
    )

    class _Boom:
        def run(self, spec, *, live):
            raise AssertionError(f"survey-failed repo must skip git: {spec.argv}")

    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Boom())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must KEEP survey-failed repo")),
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(
            tmp_path,
            working={
                "prs_by_repo": {"owner/repo": []},
                "pr_survey_failed": ["owner/repo"],
            },
        ),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["kept"][0]["reason"] == "pr_survey_failed"
    assert out["reaped_count"] == 0
    assert out["kept_count"] == 1



def test_unreadable_receipt_keeps_all_worktrees(tmp_path, monkeypatch):
    """An unparseable lifecycle file cannot be evidence that a live child is gone."""
    _corner(tmp_path, "ai/fix/142-x")
    monkeypatch.setattr(reap_stale_worktrees, "has_unreadable_issue_to_pr_receipts", lambda: True)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify unknown receipt state")),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not reap unknown receipt state")),
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )

    assert out["receipt_state_unknown"] is True
    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "receipt_state_unknown"


def test_malformed_no_pid_receipt_keeps_all_worktrees(tmp_path, monkeypatch):
    import json

    _corner(tmp_path, "ai/fix/142-x")
    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "empty.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not classify unknown receipt state")),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not reap unknown receipt state")),
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )

    assert out["receipt_state_unknown"] is True
    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "receipt_state_unknown"



def test_reap_does_not_fetch_origin_main(tmp_path, monkeypatch):
    branch = "ai/fix/142-prompt"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])

    class _NoFetch(_Git):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["fetch", "origin"]:
                raise AssertionError(f"fetch must not run during reap: {argv}")
            return super().run(spec, live=live)

    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _NoFetch())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: {
            "readable": True,
            "ahead": 1,
            "behind_main": 2,
            "published": False,
            "dirty": "empty",
            "keep_unpublished": False,
        },
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: {"ok": True, "removed": True},
    )
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["reaped_count"] == 1


def test_reap_only_inspects_mini_mill_repo(tmp_path, monkeypatch):
    """Catalog products must cause no worktree, GitHub, or remote calls."""
    mini_repo = "mikolaj92/lokay"
    product_repos = ("mikolaj92/Temida", "mikolaj92/takt")
    monkeypatch.setattr(reap_stale_worktrees, "MINI_MILL_REPO", mini_repo)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])

    branch = "ai/fix/445-reap"
    wt = tmp_path / "wt" / "mikolaj92__lokay" / "ai__fix__445-reap"
    wt.mkdir(parents=True)
    inspected: list[str] = []

    def _worktrees(cfg, repo):
        inspected.append(repo.name)
        return [(wt, branch)]

    github_calls: list[tuple[str, int]] = []

    def _closed(repo, issue):
        github_calls.append((repo, issue))
        return True

    removed: list[Path] = []
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", _worktrees)
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", _closed)
    def _no_remote_heads(*args, **kwargs):
        raise AssertionError("closed mini-mill issue skips ls-remote")

    monkeypatch.setattr(reap_stale_worktrees, "remote_heads", _no_remote_heads)
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda runner, clone, path, **kwargs: removed.append(path) or {"ok": True},
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path, repos=(*product_repos, mini_repo))),
        live=True,
    )

    assert inspected == [mini_repo]
    assert github_calls == [(mini_repo, 445)]
    assert removed == [wt]
    assert out["reaped_count"] == 1


def test_reap_skips_repos_outside_survey_scope(tmp_path, monkeypatch):
    _corner(tmp_path, "ai/fix/142-x")
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("cold repo must be skipped")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    begin_working = {"survey_repos": ["other/hot"]}
    pass_dir = _pass(tmp_path)
    from lokay.passkit import io as pass_io
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    begin["survey_repos"] = ["other/hot"]
    pass_io.write_json(pass_io.begin_path(pass_dir), begin)
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=pass_dir,
        config_path=str(_config(tmp_path)),
        live=True,
    )
    assert out["reaped_count"] == 0
    assert out["kept_count"] == 0


def test_closed_issue_reaps_without_waiting_for_over_cap(tmp_path, monkeypatch):
    branch = "ai/fix/369-closed"
    wt = _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: repo == "owner/repo" and issue == 369,
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remote_heads",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("closed issue must skip git classification")),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("closed issue must skip git classification")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    removed: list[Path] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda runner, clone, path, **kwargs: removed.append(path) or {"ok": True},
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )

    assert out["reaped_count"] == 1
    assert out["reaped"][0]["reason"] == "closed_issue"
    assert removed == [wt]




def test_hosted_closed_issue_removal_requires_healthy(tmp_path, monkeypatch):
    """Hosted worktree removal requires healthy. Classification does not."""
    branch = "ai/fix/369-closed"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", lambda *_a: True)
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda _cfg: _Git())
    removed: list[Path] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda _git, _clone, path, **_kwargs: removed.append(path) or {"ok": True},
    )

    def unhealthy(**_kwargs):
        raise RuntimeError("unhealthy")

    monkeypatch.setattr(reap_stale_worktrees, "mutations_allowed", unhealthy)
    try:
        reap_stale_worktrees.run_reap_stale_worktrees(
            pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
        )
    except RuntimeError as exc:
        assert str(exc) == "unhealthy"
    else:
        raise AssertionError("hosted removal must fail closed")
    assert removed == []
    src = Path(reap_stale_worktrees.__file__)
    assert "Hosted worktree removal requires healthy." in src.read_text(encoding="utf-8")


def test_hosted_keep_does_not_require_healthy(tmp_path, monkeypatch):
    branch = "ai/fix/369-open"
    _corner(tmp_path, branch)
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", lambda *_a: False)
    monkeypatch.setattr(reap_stale_worktrees, "remote_heads", lambda *_a: set())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *_a, **_k: {
            "readable": True,
            "ahead": 1,
            "behind_main": 0,
            "published": False,
            "dirty": "real",
            "uncommitted": "real",
            "keep_unpublished": False,
        },
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda _cfg: _Git())

    def health_boom(**_kwargs):
        raise AssertionError("hosted KEEP classification does not require healthy")

    monkeypatch.setattr(reap_stale_worktrees, "mutations_allowed", health_boom)
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )
    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "uncommitted_real"


def test_closed_issue_with_live_i2pr_is_kept(tmp_path, monkeypatch):
    branch = "ai/fix/369-closed"
    _corner(tmp_path, branch)
    monkeypatch.setattr(
        reap_stale_worktrees,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "owner/repo", "issue": 369, "pid": 61281}],
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("live writer must be checked first")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must keep live writer")),
    )

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )

    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "live_issue_to_pr"


def test_over_cap_reaps_at_most_oldest_closed_issues(tmp_path, monkeypatch):
    """A fat stack drains closed old corners without expensive classification."""
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must skip classify")),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remote_heads",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must skip ls-remote")),
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    checked: list[int] = []

    def _closed(repo, issue):
        checked.append(issue)
        return issue < cap

    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", _closed)
    removed: list[Path] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda runner, clone, path, **kwargs: removed.append(path) or {"ok": True},
    )
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 3)
    ]
    monkeypatch.setattr(reap_stale_worktrees, "_oldest", lambda rows: rows)
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers)

    pass_dir = _pass(tmp_path)
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=pass_dir,
        config_path=str(_config(tmp_path)),
        live=True,
    )

    assert checked == list(range(cap))
    assert out["reaped_count"] == cap
    assert out["kept_count"] == 3
    assert len(removed) == cap
    assert all(row["reason"] == "closed_issue" for row in out["reaped"])
    assert out["kept"] == [
        {
            "repo": "owner/repo",
            "reason": "over_cap",
            "kept": True,
            "kept_over_cap": 3,
            "reaped": cap,
            "leftover_count": cap + 3,
        }
    ]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    keep_actions = [
        row for row in working["actions"] if row["step"] == "keep_stale_worktree"
    ]
    assert keep_actions == [{"step": "keep_stale_worktree", **out["kept"][0]}]


def test_over_cap_keeps_open_issues(tmp_path, monkeypatch):
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", lambda repo, issue: False)
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must keep open issues")),
    )
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 1)
    ]
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers)

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )

    assert out["reaped_count"] == 0
    assert out["kept_count"] == cap + 1
    assert len(out["kept"]) == 1
    assert out["kept"][0]["reason"] == "over_cap"
    assert out["kept"][0]["kept_over_cap"] == cap + 1
    assert out["kept"][0]["leftover_count"] == cap + 1


def test_over_cap_no_reap_writes_stamp(tmp_path, monkeypatch):
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", lambda repo, issue: False)
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 1)
    ]
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers)
    stamp = tmp_path / "reap-over-cap.stamp"
    reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )
    assert stamp.is_file()


def test_over_cap_skips_github_when_recent_idle_stamp(tmp_path, monkeypatch):
    cap = reap_stale_worktrees.CLASSIFY_CAP
    stamp = tmp_path / "reap-over-cap.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())

    def boom(*_a, **_k):
        raise AssertionError("recent over_cap idle must not view GitHub issues")

    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", boom)
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 1)
    ]
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers)
    before = stamp.stat().st_mtime
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )
    assert out["reaped_count"] == 0
    assert out["kept"][0]["skipped"] is True
    assert out["kept"][0]["skip_reason"] == "recent_over_cap"
    assert stamp.stat().st_mtime == before


def test_pytest_does_not_skip_over_cap_github_views_using_the_mill_stamp(
    tmp_path, monkeypatch
):
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "reap-over-cap.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_over_cap_github_views_using_the_mill_stamp",
    )
    assert reap_stale_worktrees.over_cap_recently_idle(stamp) is False
    hermetic = tmp_path / "reap-over-cap.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert reap_stale_worktrees.over_cap_recently_idle(hermetic) is True
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_worktrees.py"
    )
    assert "Pytest must not skip over-cap GitHub views using the mill stamp." in src.read_text(
        encoding="utf-8"
    )


def test_over_cap_probes_when_idle_stamp_expired(tmp_path, monkeypatch):
    cap = reap_stale_worktrees.CLASSIFY_CAP
    stamp = tmp_path / "reap-over-cap.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - reap_stale_worktrees.OVER_CAP_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    checked: list[int] = []
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: checked.append(issue) or False,
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 1)
    ]
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers)
    reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )
    assert checked == list(range(cap))
    assert stamp.stat().st_mtime >= old + reap_stale_worktrees.OVER_CAP_TTL_SECONDS


def test_over_cap_reap_clears_idle_stamp(tmp_path, monkeypatch):
    cap = reap_stale_worktrees.CLASSIFY_CAP
    stamp = tmp_path / "reap-over-cap.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - reap_stale_worktrees.OVER_CAP_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", lambda repo, issue: True)
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "remove_worktree",
        lambda *a, **k: {"ok": True},
    )
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 1)
    ]
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers)
    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path), config_path=str(_config(tmp_path)), live=True
    )
    assert out["reaped_count"] == cap
    assert not stamp.exists()


def test_reap_idle_closed_worktrees_reaps_oldest_closed(tmp_path, monkeypatch):
    """Idle daemon_cycle skip still reaps CLOSED leftover mill worktrees."""
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: True,
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("idle reap must not leftover_status")
        ),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "list_uncommitted_paths",
        lambda *_a, **_k: [],
    )
    removed: list[str] = []

    def fake_remove(_git, _clone, path, **_k):
        removed.append(str(path))
        return {"ok": True, "removed": True}

    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", fake_remove)
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{i}"), f"ai/fix/{i}")
        for i in range(cap + 2)
    ]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )
    gated: list[bool] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "mutations_allowed",
        lambda **_kwargs: gated.append(True) or True,
    )
    stamp = tmp_path / "reap-over-cap.stamp"
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert gated == [True]
    assert len(removed) == cap
    assert not stamp.exists()


def test_reap_idle_closed_worktrees_classify_skips_no_issue_leftovers(
    tmp_path, monkeypatch
):
    """Idle CLASSIFY_CAP skips no-issue leftovers so Fala cannot starve mill issues."""
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )
    checked: list[int] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: checked.append(issue) or True,
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("idle reap must not leftover_status")
        ),
    )
    dirty = {"Fala": ["README.md"]}

    def fake_uncommitted(_git, path):
        branch = path.name.replace("__", "/")
        return list(dirty.get(branch, []))

    monkeypatch.setattr(
        reap_stale_worktrees, "list_uncommitted_paths", fake_uncommitted
    )
    removed: list[str] = []

    def fake_remove(_git, _clone, path, **_k):
        removed.append(Path(path).name)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", fake_remove)
    fala = _corner(tmp_path, "Fala")
    old = time.time() - 3600
    os.utime(fala, (old, old))
    issued = [
        (_corner(tmp_path, f"ai/fix/{n}"), f"ai/fix/{n}")
        for n in (123, 187, 188, 191, 192)
    ]
    leftovers = [(fala, "Fala"), *issued]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )
    gated: list[bool] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "mutations_allowed",
        lambda **_kwargs: gated.append(True) or True,
    )
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert gated == [True]
    assert "Fala" not in removed
    assert checked == [123, 187, 188, 191]
    assert removed == [
        "ai__fix__123",
        "ai__fix__187",
        "ai__fix__188",
        "ai__fix__191",
    ]
    assert cap == 4


def test_reap_idle_closed_worktrees_classify_skips_harvest_leftovers(
    tmp_path, monkeypatch
):
    """Harvest leftovers are not mill issues."""
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )
    checked: list[int] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: checked.append(issue) or True,
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("idle reap must not leftover_status")
        ),
    )
    dirty = {"harvest/414-mini-lokay-only": ["src/lokay/child_harvest.py"]}

    def fake_uncommitted(_git, path):
        branch = path.name.replace("__", "/")
        return list(dirty.get(branch, []))

    monkeypatch.setattr(
        reap_stale_worktrees, "list_uncommitted_paths", fake_uncommitted
    )
    removed: list[str] = []

    def fake_remove(_git, _clone, path, **_k):
        removed.append(Path(path).name)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", fake_remove)
    harvest = _corner(tmp_path, "harvest/414-mini-lokay-only")
    old = time.time() - 3600
    os.utime(harvest, (old, old))
    issued = [
        (_corner(tmp_path, f"ai/fix/{n}"), f"ai/fix/{n}")
        for n in (267, 269, 271, 273, 275)
    ]
    leftovers = [(harvest, "harvest/414-mini-lokay-only"), *issued]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )
    gated: list[bool] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "mutations_allowed",
        lambda **_kwargs: gated.append(True) or True,
    )
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert gated == [True]
    assert "harvest__414-mini-lokay-only" not in removed
    assert 414 not in checked
    assert checked == [267, 269, 271, 273]
    assert removed == [
        "ai__fix__267",
        "ai__fix__269",
        "ai__fix__271",
        "ai__fix__273",
    ]
    assert cap == 4


def test_reap_idle_closed_worktrees_reaps_empty_no_issue_leftovers(
    tmp_path, monkeypatch
):
    """Idle CLASSIFY_CAP reaps empty no-issue leftovers so harvest leftovers cannot freeze mill porcelain."""
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )
    checked: list[int] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: checked.append(issue) or True,
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("idle reap must not leftover_status")
        ),
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "list_uncommitted_paths",
        lambda *_a, **_k: [],
    )
    removed: list[str] = []

    def fake_remove(_git, _clone, path, **_k):
        removed.append(Path(path).name)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", fake_remove)
    harvest = _corner(tmp_path, "harvest/414-mini-lokay-only")
    old = time.time() - 3600
    os.utime(harvest, (old, old))
    issued = [
        (_corner(tmp_path, f"ai/fix/{n}"), f"ai/fix/{n}")
        for n in (291, 294, 296, 298, 300)
    ]
    leftovers = [(harvest, "harvest/414-mini-lokay-only"), *issued]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )
    gated: list[bool] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "mutations_allowed",
        lambda **_kwargs: gated.append(True) or True,
    )
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert gated == [True]
    assert "harvest__414-mini-lokay-only" in removed
    assert 414 not in checked
    assert checked == [291, 294, 296, 298]
    assert removed == [
        "harvest__414-mini-lokay-only",
        "ai__fix__291",
        "ai__fix__294",
        "ai__fix__296",
        "ai__fix__298",
    ]
    assert cap == 4


def test_reap_idle_closed_worktrees_classify_skips_dirty_real_leftovers(
    tmp_path, monkeypatch
):
    """Idle CLASSIFY_CAP skips dirty-real leftovers so KEEP cannot starve mill issues."""
    cap = reap_stale_worktrees.CLASSIFY_CAP
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )
    checked: list[int] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda repo, issue: checked.append(issue) or True,
    )
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    monkeypatch.setattr(
        reap_stale_worktrees,
        "leftover_status",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("idle reap must not leftover_status")
        ),
    )
    dirty = {
        "Fala": ["README.md"],
        "ai/fix/123": ["src/lokay/proc/compute_health.py"],
        "ai/fix/188": ["src/lokay/localize.py"],
        "ai/fix/192": ["src/lokay/proc/detach_issue_to_pr.py"],
        "ai/fix/193": ["src/lokay/proc/survey_ready.py"],
    }

    def fake_uncommitted(_git, path):
        branch = path.name.replace("__", "/")
        return list(dirty.get(branch, []))

    monkeypatch.setattr(
        reap_stale_worktrees, "list_uncommitted_paths", fake_uncommitted
    )
    removed: list[str] = []

    def fake_remove(_git, _clone, path, **_k):
        removed.append(Path(path).name)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", fake_remove)
    leftovers = [
        (_corner(tmp_path, "Fala"), "Fala"),
        *[
            (_corner(tmp_path, f"ai/fix/{n}"), f"ai/fix/{n}")
            for n in (123, 188, 192, 193, 195, 197, 199, 201)
        ],
    ]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )
    gated: list[bool] = []
    monkeypatch.setattr(
        reap_stale_worktrees,
        "mutations_allowed",
        lambda **_kwargs: gated.append(True) or True,
    )
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert gated == [True]
    assert "Fala" not in removed
    assert "ai__fix__123" not in removed
    assert "ai__fix__188" not in removed
    assert "ai__fix__192" not in removed
    assert "ai__fix__193" not in removed
    assert checked == [195, 197, 199, 201]
    assert removed == [
        "ai__fix__195",
        "ai__fix__197",
        "ai__fix__199",
        "ai__fix__201",
    ]
    assert cap == 4


def test_reap_idle_keep_only_leftovers_write_over_cap_stamp(tmp_path, monkeypatch):
    """Idle KEEP-only leftovers still write the over-cap stamp."""
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )

    def boom(*_a, **_k):
        raise AssertionError("KEEP-only idle must not view GitHub issues")

    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", boom)
    monkeypatch.setattr(reap_stale_worktrees, "make_runner", lambda cfg: _Git())
    dirty = {
        "ai/fix/123": ["src/lokay/proc/compute_health.py"],
        "ai/fix/188": ["src/lokay/localize.py"],
        "ai/fix/192": ["src/lokay/proc/detach_issue_to_pr.py"],
        "ai/fix/193": ["src/lokay/proc/survey_ready.py"],
        "ai/fix/205": ["src/lokay/proc/select_implement.py"],
    }

    def fake_uncommitted(_git, path):
        branch = path.name.replace("__", "/")
        return list(dirty.get(branch, ["src/lokay/proc/compute_health.py"]))

    monkeypatch.setattr(
        reap_stale_worktrees, "list_uncommitted_paths", fake_uncommitted
    )
    removed: list[str] = []

    def fake_remove(_git, _clone, path, **_k):
        removed.append(Path(path).name)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", fake_remove)
    leftovers = [
        (_corner(tmp_path, f"ai/fix/{n}"), f"ai/fix/{n}")
        for n in (123, 188, 192, 193, 205, 259)
    ]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )

    def health_boom(**_kwargs):
        raise AssertionError("KEEP classification and stamping do not require healthy")

    monkeypatch.setattr(reap_stale_worktrees, "mutations_allowed", health_boom)
    stamp = tmp_path / "reap-over-cap.stamp"
    assert not stamp.exists()
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert removed == []
    assert stamp.is_file()


def test_idle_over_cap_skip_outlives_leftover_probe(tmp_path, monkeypatch):
    """Idle over-cap skip outlives leftover-probe. Hosted factory_pass stays 300s."""
    stamp = tmp_path / "reap-over-cap.stamp"
    stamp.write_text("1", encoding="utf-8")
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    monkeypatch.setattr(reap_stale_worktrees, "live_issue_to_pr_receipts", lambda: [])
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )

    def boom(*_a, **_k):
        raise AssertionError("idle over-cap skip outlives leftover-probe")

    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", boom)
    monkeypatch.setattr(reap_stale_worktrees, "list_uncommitted_paths", boom)
    monkeypatch.setattr(reap_stale_worktrees, "iter_worktrees", boom)
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert stamp.stat().st_mtime == leftover_age
    assert reap_stale_worktrees.over_cap_recently_idle(stamp) is False
    assert reap_stale_worktrees.over_cap_recently_idle(
        stamp, ttl=reap_stale_worktrees.IDLE_OVER_CAP_TTL_SECONDS
    ) is True


def test_reap_idle_closed_worktrees_skips_when_not_live(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reap_stale_worktrees,
        "_issue_is_closed",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("not-live skip does not reap")),
    )
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(tmp_path / "missing.yaml"), live=False
    )


def test_reap_idle_closed_worktrees_skips_fresh_over_cap_stamp(tmp_path, monkeypatch):
    stamp = tmp_path / "reap-over-cap.stamp"
    stamp.write_text("1", encoding="utf-8")
    before = stamp.stat().st_mtime

    def boom(*_a, **_k):
        raise AssertionError("fresh over_cap idle must not view GitHub issues")

    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", boom)
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )
    assert stamp.stat().st_mtime == before


def test_reap_idle_closed_worktrees_keeps_live_i2pr(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reap_stale_worktrees,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "owner/repo", "issue": 54, "pid": 61281}],
    )
    monkeypatch.setattr(
        reap_stale_worktrees,
        "has_unreadable_issue_to_pr_receipts",
        lambda: False,
    )

    def boom(*_a, **_k):
        raise AssertionError("live i2pr must not classify leftover worktrees")

    monkeypatch.setattr(reap_stale_worktrees, "_issue_is_closed", boom)
    monkeypatch.setattr(reap_stale_worktrees, "remove_worktree", boom)
    leftovers = [(_corner(tmp_path, "ai/fix/16"), "ai/fix/16")]
    monkeypatch.setattr(
        reap_stale_worktrees, "iter_worktrees", lambda cfg, repo: leftovers
    )
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(_config(tmp_path)), live=True
    )


def test_reap_idle_closed_worktrees_oserror_cannot_stall(tmp_path, monkeypatch):
    def boom(*_a, **_k):
        raise OSError("config unreadable")

    monkeypatch.setattr(reap_stale_worktrees, "load_cfg", boom)
    reap_stale_worktrees.reap_idle_closed_worktrees(
        config_path=str(tmp_path / "missing.yaml"), live=True
    )

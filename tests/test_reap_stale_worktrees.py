"""reap_stale_worktrees: KEEP live / covering / dirty unpublished; REMOVE stale."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from lokay.passkit import io as pass_io
from lokay.proc import reap_stale_worktrees


def _ok() -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout="", stderr="")


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

    out = reap_stale_worktrees.run_reap_stale_worktrees(
        pass_dir=_pass(tmp_path),
        config_path=str(_config(tmp_path)),
        live=True,
    )

    assert checked == list(range(cap))
    assert out["reaped_count"] == cap
    assert len(removed) == cap
    assert all(row["reason"] == "closed_issue" for row in out["reaped"])
    assert len([row for row in out["kept"] if row["reason"] == "over_cap"]) == 3


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
    assert all(row["reason"] == "over_cap" for row in out["kept"])

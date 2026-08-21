"""worktree --reset-base flag wiring (no live git)."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from lokay.config import Config, RepoConfig
from lokay.git_worktree import InvalidBranchRef, assert_valid_branch_ref, ensure_worktree, leftover_status, remote_heads, remove_worktree
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


def test_worktree_add_maps_check_ref_format_fail_to_invalid_branch_ref(
    tmp_path, monkeypatch, capsys
):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: live
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
  - name: mikolaj92/lokay
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
    monkeypatch.setattr(worktree_add, "mutations_allowed", lambda **kw: True)

    def boom(*_a, **_kw):
        raise InvalidBranchRef("ai/fix/7-foo-..-bar", "not a valid branch name")

    monkeypatch.setattr(worktree_add, "ensure_worktree", boom)
    code = worktree_add.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "mikolaj92/lokay",
            "--branch",
            "ai/fix/7-foo-..-bar",
            "--live",
        ]
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 1
    assert payload["ok"] is False
    assert payload["reason"] == "invalid_branch_ref"


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
        if argv[1:3] == ["fetch", "origin"] and len(argv) > 3 and argv[3] != "main":
            return _result(
                argv,
                returncode=getattr(self, "branch_fetch_rc", 0),
                stderr="couldn't find remote ref" if getattr(self, "branch_fetch_rc", 0) else "",
            )
        if argv[1:4] == ["rev-list", "--count", "origin/main..HEAD"]:
            return _result(argv, returncode=self.ahead_rc, stdout=(self.ahead or "") + "\n")
        if argv[1:4] == ["rev-list", "--count", "HEAD..origin/main"]:
            return _result(argv, stdout=str(getattr(self, "behind_main", 0)) + "\n")
        if argv[1:3] == ["rev-list", "--count"] and "HEAD..origin/" in argv[3]:
            return _result(argv, stdout=str(getattr(self, "behind", 0)) + "\n")
        if argv[1] == "diff" or argv[1] == "ls-files":
            return _result(argv, stdout=getattr(self, "diff_names", ""))
        if argv[1:3] == ["worktree", "remove"]:
            target = Path(argv[3])
            if target.exists():
                target.rmdir()
            return _result(argv)
        if argv[1:4] == ["worktree", "list", "--porcelain"]:
            clone = Path(spec.cwd).resolve()
            records = [
                f"worktree {clone}\0HEAD {'d' * 40}\0branch refs/heads/main\0"
            ]
            for path in sorted(clone.parent.rglob("*")):
                if path.is_dir() and path != clone and not path.is_symlink():
                    records.append(
                        f"worktree {path.resolve()}\0HEAD {'c' * 40}\0branch refs/heads/fix\0"
                    )
            return _result(argv, stdout="\0".join(records) + "\0")
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


def test_reset_to_base_keeps_unpublished_ahead(tmp_path):
    """Timeout leftover that never pushed: no origin/<branch> → KEEP."""
    branch = "ai/fix/164-observe"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    runner.branch_fetch_rc = 128
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    destructive = {"remove", "add", "push"}
    assert not any(call[1] in destructive for call in runner.calls)
    assert any(call[1:4] == ["rev-list", "--count", "origin/main..HEAD"] for call in runner.calls)


def test_reset_to_base_rewrites_unpublished_behind_main(tmp_path):
    """rebase_conflict leftover: never pushed, but origin/main moved → RESET."""
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="5")
    runner.branch_fetch_rc = 128
    runner.behind_main = 4
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)
    assert any(call[1:3] == ["worktree", "add"] and "-B" in call for call in runner.calls)


def test_reset_to_base_rewrites_published_even_if_current(tmp_path):
    """Closed CONFLICTING tip matches HEAD: KEEP would republish the same dirty PR."""
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="8")
    runner.behind = 0
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)
    assert any(call[1:3] == ["worktree", "add"] and "-B" in call for call in runner.calls)
    assert any(call[1:4] == ["push", "origin", "--delete"] for call in runner.calls)


def test_reset_to_base_rewrites_when_ahead_zero(tmp_path):
    branch = "ai/fix/164-observe"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="0")
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)
    assert any(call[1:3] == ["worktree", "add"] and "-B" in call for call in runner.calls)
    assert any(call[1:4] == ["push", "origin", "--delete"] for call in runner.calls)


def test_reset_to_base_rewrites_when_ahead_but_behind_own_remote(tmp_path):
    """NFF reuse: unpublished vs main AND behind origin/<branch> → new corner."""
    branch = "ai/fix/86-nff"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="11")
    runner.behind = 3
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)
    assert any(call[1:3] == ["worktree", "add"] and "-B" in call for call in runner.calls)
    assert any(call[1:4] == ["push", "origin", "--delete"] for call in runner.calls)


def test_reset_to_base_keeps_dirty_real_tree_when_unpublished_behind_main(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="5")
    runner.branch_fetch_rc = 128
    runner.behind_main = 4
    runner.diff_names = "UNCOMMITTED_IMPORTANT\n"

    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )

    assert path == wt
    assert not any(call[1] == "worktree" and call[2] == "remove" for call in runner.calls)
    assert not any(call[1] == "worktree" and call[2] == "add" for call in runner.calls)


def test_reset_to_base_keeps_dirty_real_tree_when_branch_is_published(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="8")
    runner.behind = 0
    runner.diff_names = "src/lokay/partial_fix.py\n"

    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )

    assert path == wt
    assert not any(call[1] == "worktree" and call[2] == "remove" for call in runner.calls)
    assert not any(call[1] == "push" and "--delete" in call for call in runner.calls)


def test_reset_to_base_keeps_dirty_real_tree(tmp_path):
    """Timeout leftover: no commit yet, but real files in the tree → KEEP."""
    branch = "ai/fix/62-timeout"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="0")
    runner.diff_names = "src/lokay/agent.py\n"
    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )
    assert path == wt
    assert not any(call[1] == "remove" for call in runner.calls)
    assert not any(call[1] == "add" for call in runner.calls)


def test_reset_to_base_resets_plan_only_uncommitted_evidence(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="8")
    runner.behind = 0
    runner.diff_names = ".lokay/approach.md\n.lokay/localize.json\n"

    path = ensure_worktree(
        runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
    )

    assert path == wt
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)


def test_reset_to_base_fails_closed_when_uncommitted_state_is_unreadable(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, _wt = _cfg_repo(tmp_path, branch)

    class _UnreadableDirty(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["diff", "--name-only", "--cached"]:
                self.calls.append(argv)
                return _result(argv, returncode=128, stderr="cannot read index")
            return super().run(spec, live=live)

    runner = _UnreadableDirty(ahead="8")
    with pytest.raises(RuntimeError, match="cannot inspect uncommitted"):
        ensure_worktree(
            runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
        )
    assert not any(call[1:3] == ["worktree", "remove"] for call in runner.calls)


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


def test_reset_to_base_fail_closed_when_branch_fetch_flakes(tmp_path):
    """Network flake is not 'unpublished' — do not KEEP a maybe-published tip."""
    branch = "ai/fix/142-prompt"
    cfg, repo, _wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="8")
    runner.branch_fetch_rc = 128
    runner.branch_fetch_stderr = "fatal: unable to access 'https://github.com/': Could not resolve host"
    # override default missing-ref stderr
    orig_run = runner.run

    def run(spec, *, live):
        argv = list(spec.argv)
        if argv[1:3] == ["fetch", "origin"] and len(argv) > 3 and argv[3] != "main":
            runner.calls.append(argv)
            return _result(argv, returncode=128, stderr=runner.branch_fetch_stderr)
        return orig_run(spec, live=live)

    runner.run = run  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="origin/"):
        ensure_worktree(
            runner, cfg, repo, branch, live=True, base="main", reset_to_base=True
        )
    assert not any(call[1] == "remove" for call in runner.calls)
    assert not any(call[1] == "add" for call in runner.calls)


def test_leftover_status_keeps_unpublished_ahead(tmp_path):
    branch = "ai/fix/164-observe"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    runner.branch_fetch_rc = 128
    status = leftover_status(runner, wt, repo.clone_path, branch)
    assert status["readable"] is True
    assert status["published"] is False
    assert status["keep_unpublished"] is True


def test_leftover_status_does_not_keep_unpublished_behind_main(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    runner.branch_fetch_rc = 128
    runner.behind_main = 4
    status = leftover_status(runner, wt, repo.clone_path, branch)
    assert status["readable"] is True
    assert status["published"] is False
    assert status["keep_unpublished"] is False


def test_leftover_status_marks_published_tip(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    status = leftover_status(runner, wt, repo.clone_path, branch)
    assert status["readable"] is True
    assert status["published"] is True
    assert status["keep_unpublished"] is False


def test_leftover_status_keeps_dirty_unpublished(tmp_path):
    branch = "ai/fix/54-x"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="0")
    runner.branch_fetch_rc = 128
    runner.diff_names = "src/app.py\n"
    status = leftover_status(runner, wt, repo.clone_path, branch)
    assert status["keep_unpublished"] is True
    assert status["dirty"] == "real"


def test_leftover_status_reports_real_uncommitted_on_published_tip(tmp_path):
    branch = "ai/fix/54-x"
    _cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="2")
    runner.behind = 0
    runner.diff_names = "src/partial.py\n"

    status = leftover_status(runner, wt, repo.clone_path, branch)

    assert status["published"] is True
    assert status["uncommitted"] == "real"


def test_leftover_status_fails_closed_when_uncommitted_state_is_unreadable(tmp_path):
    branch = "ai/fix/54-x"
    _cfg, repo, wt = _cfg_repo(tmp_path, branch)

    class _Unreadable(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["diff", "--name-only", "--cached"]:
                self.calls.append(argv)
                return _result(argv, returncode=128, stderr="cannot read index")
            return super().run(spec, live=live)

    status = leftover_status(_Unreadable(ahead="2"), wt, repo.clone_path, branch)

    assert status["readable"] is False
    assert "cannot read index" in status["error"]


def test_leftover_status_fail_closed_on_branch_fetch_flake(tmp_path):
    branch = "ai/fix/54-x"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)

    class _Flake(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["fetch", "origin"] and len(argv) > 3 and argv[3] != "main":
                self.calls.append(argv)
                return _result(
                    argv,
                    returncode=128,
                    stderr="unable to access 'https://github.com/': Could not resolve host",
                )
            return super().run(spec, live=live)

    status = leftover_status(_Flake(ahead="2"), wt, repo.clone_path, branch)
    assert status["readable"] is False
    assert "unable to access" in str(status.get("error") or "")


def test_remove_worktree_already_gone(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    missing = tmp_path / "gone"
    runner = _ResetRunner()
    out = remove_worktree(runner, clone, missing, managed_root=tmp_path)
    assert out == {"ok": True, "removed": False, "already_gone": True}
    assert not any(call[1] == "worktree" for call in runner.calls)



def test_remove_worktree_archives_bytes_after_registry_prune(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()
    (corner / "tracked.txt").write_text("preserve snapshot\n", encoding="utf-8")
    runner = _ResetRunner()

    out = remove_worktree(runner, clone, corner, managed_root=tmp_path)

    archive = Path(out["preserved_path"])
    assert out["ok"] is True
    assert out["removed"] is True
    assert not corner.exists()
    assert (archive / "tracked.txt").read_text(encoding="utf-8") == "preserve snapshot\n"
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)
    assert not any(call[1:3] == ["worktree", "remove"] for call in runner.calls)

def test_remove_worktree_uses_next_archive_name_without_overwriting_old_archive(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()
    (corner / "snapshot.txt").write_text("new snapshot\n", encoding="utf-8")
    old_archive = tmp_path / ".corner.lokay-preserved"
    old_archive.mkdir()
    (old_archive / "valuable").write_text("keep\n", encoding="utf-8")

    out = remove_worktree(_ResetRunner(), clone, corner, managed_root=tmp_path)

    archive = Path(out["preserved_path"])
    assert out["ok"] is True
    assert out["removed"] is True
    assert archive == tmp_path / ".corner-2.lokay-preserved"
    assert (old_archive / "valuable").read_text(encoding="utf-8") == "keep\n"
    assert (archive / "snapshot.txt").read_text(encoding="utf-8") == "new snapshot\n"
    assert not corner.exists()


def test_remove_worktree_restores_path_when_registry_prune_fails(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "foreign"
    corner.mkdir()

    class Refuses(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["worktree", "prune"]:
                return _result(argv, returncode=128, stderr="fatal: registry locked")
            return super().run(spec, live=live)

    out = remove_worktree(Refuses(), clone, corner, managed_root=tmp_path)

    assert out["ok"] is False
    assert "registry locked" in out["error"]
    assert not corner.exists()
    assert Path(out["preserved_path"]).is_dir()

def test_remove_worktree_keeps_path_when_clone_still_lists_it(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "locked"
    corner.mkdir()

    class _StillOwned(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            self.calls.append(argv)
            if argv[1:4] == ["worktree", "list", "--porcelain"]:
                return _result(
                    argv,
                    stdout=(
                        f"worktree {clone}\0HEAD cccccccccccccccccccccccccccccccccccccccc\0branch refs/heads/main\0\0"
                        f"worktree {corner}\0HEAD dddddddddddddddddddddddddddddddddddddddd\0branch refs/heads/fix\0\0"
                    ),
                )
            return _result(argv)

    runner = _StillOwned()
    out = remove_worktree(runner, clone, corner, managed_root=tmp_path)

    assert out["ok"] is False
    assert out["removed"] is False
    assert out["error"] == "git still owns worktree after registry prune"
    assert Path(out["preserved_path"]).is_dir()
    assert not corner.exists()


def test_remove_worktree_keeps_path_when_post_remove_registry_is_empty(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()
    class _EmptyRegistry(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["worktree", "list", "--porcelain"]:
                self.calls.append(argv)
                return _result(argv, stdout="")
            return super().run(spec, live=live)

    out = remove_worktree(_EmptyRegistry(), clone, corner, managed_root=tmp_path)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership before preservation",
    }
    assert corner.is_dir()


def test_remove_worktree_keeps_path_when_post_remove_registry_is_truncated(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()

    class _TruncatedRegistry(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            self.calls.append(argv)
            if argv[1:4] == ["worktree", "list", "--porcelain"]:
                return _result(argv, stdout=f"worktree {clone}\0HEAD dddddddddddddddddddddddddddddddddddddddd\0")
            return _result(argv)

    out = remove_worktree(_TruncatedRegistry(), clone, corner, managed_root=tmp_path)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership before preservation",
    }
    assert corner.is_dir()


def test_remove_worktree_keeps_path_when_post_remove_registry_is_unreadable(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()

    class _NoRegistry(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            self.calls.append(argv)
            if argv[1:4] == ["worktree", "list", "--porcelain"]:
                return _result(argv, returncode=128, stderr="registry unavailable")
            return _result(argv)

    runner = _NoRegistry()
    out = remove_worktree(runner, clone, corner, managed_root=tmp_path)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership before preservation",
    }
    assert corner.is_dir()

def test_leftover_status_known_published_skips_branch_fetch(tmp_path):
    branch = "ai/fix/142-prompt"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    status = leftover_status(
        runner, wt, repo.clone_path, branch, known_published=True
    )
    assert status["published"] is True
    assert status["keep_unpublished"] is False
    assert not any(
        call[1:3] == ["fetch", "origin"] and len(call) > 3 and call[3] != "main"
        for call in runner.calls
    )


def test_leftover_status_known_unpublished_skips_branch_fetch(tmp_path):
    branch = "ai/fix/164-observe"
    cfg, repo, wt = _cfg_repo(tmp_path, branch)
    runner = _ResetRunner(ahead="3")
    status = leftover_status(
        runner, wt, repo.clone_path, branch, known_published=False
    )
    assert status["published"] is False
    assert status["keep_unpublished"] is True
    assert not any(
        call[1:3] == ["fetch", "origin"] and len(call) > 3 and call[3] != "main"
        for call in runner.calls
    )


def test_remote_heads_lists_origin():
    class _Heads(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["ls-remote", "--heads", "origin"]:
                return _result(
                    argv,
                    stdout="abc\trefs/heads/ai/fix/142-x\ndef\trefs/heads/main\n",
                )
            return super().run(spec, live=live)

    heads = remote_heads(_Heads(), Path("/tmp"))
    assert heads == {"ai/fix/142-x", "main"}


def test_remote_heads_fail_closed():
    class _Fail(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["ls-remote", "--heads", "origin"]:
                return _result(argv, returncode=128, stderr="unable to access")
            return super().run(spec, live=live)

    assert remote_heads(_Fail(), Path("/tmp")) is None


def test_list_uncommitted_paths_includes_ignored_user_data_but_not_caches(tmp_path):
    import subprocess

    from lokay.git_real_diff import list_uncommitted_paths

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text(
        "important.secret\ntrailing \n.venv/\n__pycache__/\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "base"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "important.secret").write_text("do not delete\n", encoding="utf-8")
    (tmp_path / "trailing ").write_text("also keep\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "cache").write_text("generated\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"generated")

    assert list_uncommitted_paths(Runner(), tmp_path) == [
        "important.secret",
        "trailing ",
    ]


def test_remove_worktree_rejects_symlink_without_git(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    managed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = managed / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    runner = _ResetRunner()

    out = remove_worktree(
        runner,
        clone,
        alias,
        managed_root=managed,
    )

    assert out["ok"] is False
    assert "symlink" in out["error"]
    assert outside.is_dir()
    assert runner.calls == []


def test_remove_worktree_rejects_path_outside_managed_root(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    managed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    runner = _ResetRunner()

    out = remove_worktree(
        runner,
        clone,
        outside,
        managed_root=managed,
    )

    assert out["ok"] is False
    assert "outside managed root" in out["error"]
    assert outside.is_dir()
    assert runner.calls == []


def test_iter_worktrees_ignores_symlink_corners(tmp_path):
    from lokay.git_worktree import iter_worktrees

    managed = tmp_path / "managed"
    repo_root = managed / "owner__repo"
    repo_root.mkdir(parents=True)
    real = repo_root / "ai__fix__1-real"
    real.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo_root / "ai__fix__2-alias").symlink_to(outside, target_is_directory=True)
    cfg = Config(worktrees_root=managed, repos=[])
    repo = RepoConfig(name="owner/repo", clone_path=tmp_path / "clone")

    assert iter_worktrees(cfg, repo) == [(real, "ai/fix/1-real")]


def test_remove_registered_worktree_preserves_ignored_user_data(tmp_path):
    import subprocess

    clone = tmp_path / "clone"
    managed = tmp_path / "managed"
    corner = managed / "owner__repo" / "ai__fix__1-x"
    clone.mkdir()
    managed.mkdir()
    subprocess.run(["git", "init"], cwd=clone, check=True, capture_output=True)
    (clone / ".gitignore").write_text("important.secret\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=clone, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "base"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(corner), "HEAD"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    important = corner / "important.secret"
    important.write_text("do not delete\n", encoding="utf-8")

    out = remove_worktree(
        Runner(),
        clone,
        corner,
        managed_root=managed,
    )

    assert out["ok"] is False
    assert "uncommitted real content" in out["error"]
    assert important.read_text(encoding="utf-8") == "do not delete\n"


def test_remove_worktree_archives_uv_lock_only_dirt(tmp_path):
    """uv.lock-only is not real uncommitted content."""
    import subprocess

    clone = tmp_path / "clone"
    managed = tmp_path / "managed"
    corner = managed / "owner__repo" / "ai__fix__16-x"
    clone.mkdir()
    managed.mkdir()
    subprocess.run(["git", "init"], cwd=clone, check=True, capture_output=True)
    (clone / "uv.lock").write_text("old\n", encoding="utf-8")
    (clone / "src.py").write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "add", "uv.lock", "src.py"], cwd=clone, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "base"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(corner), "HEAD"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    (corner / "uv.lock").write_text("new\n", encoding="utf-8")

    out = remove_worktree(
        Runner(),
        clone,
        corner,
        managed_root=managed,
    )

    archive = Path(out["preserved_path"])
    assert out["ok"] is True
    assert out["removed"] is True
    assert not corner.exists()
    assert (archive / "uv.lock").read_text(encoding="utf-8") == "new\n"
    assert (archive / "src.py").read_text(encoding="utf-8") == "ok\n"


def test_remove_worktree_never_recursively_deletes_late_content(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    corner = managed / "corner"
    corner.mkdir(parents=True)

    class LateContent(_ResetRunner):
        def __init__(self):
            super().__init__()
            self.list_count = 0

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["worktree", "list", "--porcelain"]:
                self.calls.append(argv)
                self.list_count += 1
                records = f"worktree {clone}\0HEAD {'d' * 40}\0branch refs/heads/main\0"
                if self.list_count == 1:
                    records += f"\0worktree {corner}\0HEAD {'c' * 40}\0branch refs/heads/fix\0"
                return _result(argv, stdout=records + "\0")
            if argv[1:3] == ["worktree", "prune"]:
                self.calls.append(argv)
                archive = corner.with_name(f".{corner.name}.lokay-preserved")
                (archive / "late.txt").write_text("late work\n", encoding="utf-8")
                return _result(argv)
            return super().run(spec, live=live)

    runner = LateContent()
    out = remove_worktree(
        runner,
        clone,
        corner,
        managed_root=managed,
    )

    assert out["ok"] is True
    archive = Path(out["preserved_path"])
    assert (archive / "late.txt").read_text(encoding="utf-8") == "late work\n"
    assert not any(call[1:3] == ["worktree", "remove"] for call in runner.calls)


def test_remove_worktree_rejects_ancestor_symlink_alias_without_git(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    managed.mkdir()
    outside = tmp_path / "outside"
    corner = outside / "corner"
    corner.mkdir(parents=True)
    alias_parent = managed / "alias"
    alias_parent.symlink_to(outside, target_is_directory=True)
    alias = alias_parent / "corner"
    runner = _ResetRunner()

    out = remove_worktree(
        runner,
        clone,
        alias,
        managed_root=managed,
    )

    assert out["ok"] is False
    assert "outside managed root" in out["error"] or "does not resolve lexically" in out["error"]
    assert corner.is_dir()
    assert runner.calls == []


def test_list_uncommitted_paths_fails_closed_on_warning_only_ignored_query(tmp_path):
    from lokay.git_real_diff import list_uncommitted_paths

    class WarningIgnored(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["ls-files", "--others"] and "--ignored" in argv:
                return _result(argv, stderr="warning: ignored paths omitted")
            return super().run(spec, live=live)

    with pytest.raises(RuntimeError, match="ignored paths omitted"):
        list_uncommitted_paths(WarningIgnored(), tmp_path)


def test_remove_worktree_native_late_ignored_file_is_archived(tmp_path):
    import subprocess

    clone = tmp_path / "clone"
    managed = tmp_path / "managed"
    corner = managed / "owner__repo" / "ai__fix__1-x"
    clone.mkdir()
    managed.mkdir()
    subprocess.run(["git", "init"], cwd=clone, check=True, capture_output=True)
    (clone / ".gitignore").write_text("*.secret\n", encoding="utf-8")
    (clone / "tracked").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=clone, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "base"],
        cwd=clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(corner), "HEAD"],
        cwd=clone,
        check=True,
        capture_output=True,
    )

    class Inject(Runner):
        def run(self, spec, *, live):
            if list(spec.argv)[1:3] == ["worktree", "prune"]:
                archive = corner.with_name(f".{corner.name}.lokay-preserved")
                (archive / "late.secret").write_text("IRREPLACEABLE", encoding="utf-8")
            return super().run(spec, live=live)

    out = remove_worktree(Inject(), clone, corner, managed_root=managed)

    archive = Path(out["preserved_path"])
    assert out["ok"] is True
    assert not corner.exists()
    assert (archive / "late.secret").read_text(encoding="utf-8") == "IRREPLACEABLE"
    listed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=clone,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert str(corner.resolve()) not in listed


def test_iter_worktrees_excludes_only_preserved_namespace(tmp_path):
    from lokay.git_worktree import iter_worktrees

    managed = tmp_path / "managed"
    repo_root = managed / "owner__repo"
    repo_root.mkdir(parents=True)
    archive = repo_root / ".ai__fix__1-old.lokay-preserved"
    archive.mkdir()
    ordinary_hidden = repo_root / ".ordinary"
    ordinary_hidden.mkdir()
    cfg = Config(worktrees_root=managed, repos=[])
    repo = RepoConfig(name="owner/repo", clone_path=tmp_path / "clone")

    assert iter_worktrees(cfg, repo) == [(ordinary_hidden, ".ordinary")]


def test_remove_worktree_fails_closed_on_warning_only_registry_query(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()

    class WarningRegistry(_ResetRunner):
        def run(self, spec, *, live):
            result = super().run(spec, live=live)
            if list(spec.argv)[1:4] == ["worktree", "list", "--porcelain"]:
                result.stderr = "warning: registry may be incomplete"
            return result

    out = remove_worktree(WarningRegistry(), clone, corner, managed_root=tmp_path)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership before preservation",
    }
    assert corner.is_dir()


def test_remove_worktree_fails_closed_on_interrupted_preservation_archive(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    archive = tmp_path / ".corner.lokay-preserved"
    archive.mkdir()
    (archive / "valuable").write_text("keep\n", encoding="utf-8")

    out = remove_worktree(_ResetRunner(), clone, corner, managed_root=tmp_path)

    assert out["ok"] is False
    assert out["preserved_path"] == str(archive)
    assert "requires reconciliation" in out["error"]
    assert (archive / "valuable").read_text(encoding="utf-8") == "keep\n"


def test_remove_worktree_restores_path_on_warning_only_registry_prune(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()

    class WarningPrune(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["worktree", "prune"]:
                return _result(argv, stderr="warning: prune incomplete")
            return super().run(spec, live=live)

    out = remove_worktree(WarningPrune(), clone, corner, managed_root=tmp_path)

    assert out["ok"] is False
    assert "prune incomplete" in out["error"]
    assert not corner.exists()
    assert Path(out["preserved_path"]).is_dir()


def test_backslash_filename_cannot_alias_plan_evidence(tmp_path):
    import subprocess

    from lokay.git_real_diff import classify_changed_paths, list_uncommitted_paths

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text("*\\approach.md\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "base"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / ".lokay\approach.md").write_text("real user data\n", encoding="utf-8")

    paths = list_uncommitted_paths(Runner(), tmp_path)
    assert paths == [".lokay\approach.md"]
    assert classify_changed_paths(paths) == "real"


def test_remove_worktree_restore_never_overwrites_replacement_after_parent_swap(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    parent = managed / "owner__repo"
    corner = parent / "ai__fix__1-x"
    corner.mkdir(parents=True)
    (corner / "source.txt").write_text("DECOY SOURCE\n", encoding="utf-8")

    class SwapParent(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["worktree", "prune"]:
                outside = tmp_path / "outside"
                outside.mkdir()
                parent.rename(outside / "owner__repo")
                parent.symlink_to(outside / "owner__repo", target_is_directory=True)
                victim = parent / "ai__fix__1-x"
                victim.mkdir()
                (victim / "source.txt").write_text("VALUABLE VICTIM\n", encoding="utf-8")
                return _result(argv, stderr="warning: prune uncertain")
            return super().run(spec, live=live)

    out = remove_worktree(SwapParent(), clone, corner, managed_root=managed)

    victim = parent / "ai__fix__1-x"
    archive = parent / ".ai__fix__1-x.lokay-preserved"
    assert out["ok"] is False
    assert out["removed"] is False
    assert victim.is_dir()
    assert (victim / "source.txt").read_text(encoding="utf-8") == "VALUABLE VICTIM\n"
    assert archive.is_dir()
    assert (archive / "source.txt").read_text(encoding="utf-8") == "DECOY SOURCE\n"
    assert "prune uncertain" in out["error"]


def test_remove_worktree_parent_swap_before_pin_cannot_move_outside_victim(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    parent = managed / "owner__repo"
    corner = parent / "ai__fix__1-x"
    corner.mkdir(parents=True)
    (corner / "registered.txt").write_text("REGISTERED\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside_parent = outside / "owner__repo"
    outside_corner = outside_parent / "ai__fix__1-x"
    outside_corner.mkdir(parents=True)
    (outside_corner / "victim.txt").write_text("VALUABLE OUTSIDE\n", encoding="utf-8")

    class SwapBeforePin(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["worktree", "list"] and not parent.is_symlink():
                displaced = tmp_path / "displaced"
                parent.rename(displaced)
                parent.symlink_to(outside_parent, target_is_directory=True)
            return super().run(spec, live=live)

    out = remove_worktree(SwapBeforePin(), clone, corner, managed_root=managed)

    assert out["ok"] is False
    assert out["removed"] is False
    assert "changed before preservation" in out["error"]
    assert outside_corner.is_dir()
    assert (outside_corner / "victim.txt").read_text(encoding="utf-8") == "VALUABLE OUTSIDE\n"
    assert not (outside_parent / ".ai__fix__1-x.lokay-preserved").exists()
    assert (tmp_path / "displaced" / "ai__fix__1-x" / "registered.txt").read_text(
        encoding="utf-8"
    ) == "REGISTERED\n"


def test_remove_worktree_root_swap_before_open_cannot_move_outside_victim(
    tmp_path, monkeypatch
):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    parent = managed / "owner__repo"
    corner = parent / "ai__fix__1-x"
    corner.mkdir(parents=True)
    (corner / "registered.txt").write_text("REGISTERED\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside_parent = outside / "owner__repo"
    outside_corner = outside_parent / "ai__fix__1-x"
    outside_corner.mkdir(parents=True)
    (outside_corner / "victim.txt").write_text("VALUABLE OUTSIDE\n", encoding="utf-8")
    real_open = os.open
    swapped = False

    def swap_before_root_open(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal swapped
        if not swapped and dir_fd is not None and path == managed.name:
            swapped = True
            displaced = tmp_path / "displaced-managed"
            managed.rename(displaced)
            managed.symlink_to(outside, target_is_directory=True)
        if dir_fd is None:
            return real_open(path, flags, *args, **kwargs)
        return real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

    monkeypatch.setattr(os, "open", swap_before_root_open)
    out = remove_worktree(_ResetRunner(), clone, corner, managed_root=managed)

    assert out["ok"] is False
    assert out["removed"] is False
    assert outside_corner.is_dir()
    assert (outside_corner / "victim.txt").read_text(encoding="utf-8") == "VALUABLE OUTSIDE\n"
    assert not (outside_parent / ".ai__fix__1-x.lokay-preserved").exists()
    assert (
        tmp_path / "displaced-managed" / "owner__repo" / "ai__fix__1-x" / "registered.txt"
    ).read_text(encoding="utf-8") == "REGISTERED\n"


def test_remove_worktree_container_swap_before_open_cannot_move_outside_victim(
    tmp_path, monkeypatch
):
    container = tmp_path / "container"
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = container / "managed"
    parent = managed / "owner__repo"
    corner = parent / "ai__fix__1-x"
    corner.mkdir(parents=True)
    (corner / "registered.txt").write_text("REGISTERED\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside_managed = outside / "managed"
    outside_parent = outside_managed / "owner__repo"
    outside_corner = outside_parent / "ai__fix__1-x"
    outside_corner.mkdir(parents=True)
    (outside_corner / "victim.txt").write_text("VALUABLE OUTSIDE\n", encoding="utf-8")
    real_open = os.open
    swapped = False

    def swap_before_any_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if not swapped:
            swapped = True
            displaced = tmp_path / "displaced-container"
            container.rename(displaced)
            container.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_before_any_open)
    out = remove_worktree(_ResetRunner(), clone, corner, managed_root=managed)

    assert out["ok"] is False
    assert out["removed"] is False
    assert outside_corner.is_dir()
    assert (outside_corner / "victim.txt").read_text(encoding="utf-8") == "VALUABLE OUTSIDE\n"
    assert not (outside_parent / ".ai__fix__1-x.lokay-preserved").exists()
    assert (
        tmp_path
        / "displaced-container"
        / "managed"
        / "owner__repo"
        / "ai__fix__1-x"
        / "registered.txt"
    ).read_text(encoding="utf-8") == "REGISTERED\n"


def test_remove_worktree_rejects_dotdot_escape_without_git(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    managed.mkdir()
    outside = tmp_path / "outside"
    corner = outside / "ai__fix__1-x"
    corner.mkdir(parents=True)
    (corner / "victim.txt").write_text("VALUABLE OUTSIDE\n", encoding="utf-8")
    escaped = managed / ".." / "outside" / "ai__fix__1-x"

    out = remove_worktree(_ResetRunner(), clone, escaped, managed_root=managed)

    assert out["ok"] is False
    assert out["removed"] is False
    assert "outside managed root" in out["error"] or "lexical" in out["error"]
    assert corner.is_dir()
    assert (corner / "victim.txt").read_text(encoding="utf-8") == "VALUABLE OUTSIDE\n"
    assert not (outside / ".ai__fix__1-x.lokay-preserved").exists()


def test_remove_worktree_last_component_swap_at_rename_does_not_prune(tmp_path, monkeypatch):
    clone = tmp_path / "clone"
    clone.mkdir()
    managed = tmp_path / "managed"
    parent = managed / "owner__repo"
    corner = parent / "ai__fix__1-x"
    corner.mkdir(parents=True)
    (corner / "registered.txt").write_text("REGISTERED\n", encoding="utf-8")
    real_rename = os.rename
    swapped = False

    def swap_at_rename(src, dst, *args, src_dir_fd=None, dst_dir_fd=None, **kwargs):
        nonlocal swapped
        if (
            not swapped
            and src == corner.name
            and dst == f".{corner.name}.lokay-preserved"
            and src_dir_fd is not None
        ):
            swapped = True
            displaced = parent / "displaced-original"
            os.rename(corner.name, displaced.name, src_dir_fd=src_dir_fd, dst_dir_fd=src_dir_fd)
            os.mkdir(corner.name, dir_fd=src_dir_fd)
            victim = os.open(corner.name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=src_dir_fd)
            try:
                fd = os.open("VICTIM.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=victim)
                os.write(fd, b"VALUABLE REPLACEMENT\n")
                os.close(fd)
            finally:
                os.close(victim)
        if src_dir_fd is None and dst_dir_fd is None:
            return real_rename(src, dst, *args, **kwargs)
        return real_rename(
            src,
            dst,
            *args,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            **kwargs,
        )

    class Owned(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["worktree", "prune"]:
                raise AssertionError("must not prune after last-component identity mismatch")
            return super().run(spec, live=live)

    monkeypatch.setattr(os, "rename", swap_at_rename)
    out = remove_worktree(Owned(), clone, corner, managed_root=managed)

    archive = parent / ".ai__fix__1-x.lokay-preserved"
    displaced = parent / "displaced-original"
    assert out["ok"] is False
    assert out["removed"] is False
    assert "changed during preservation" in out["error"]
    assert archive.is_dir()
    assert (archive / "VICTIM.txt").read_text(encoding="utf-8") == "VALUABLE REPLACEMENT\n"
    assert displaced.is_dir()
    assert (displaced / "registered.txt").read_text(encoding="utf-8") == "REGISTERED\n"
    assert not corner.exists()

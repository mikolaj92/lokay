"""worktree --reset-base flag wiring (no live git)."""

import json
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
    monkeypatch.setattr(worktree_add, "mutations_allowed", lambda **kw: True)

    def boom(*_a, **_kw):
        raise InvalidBranchRef("ai/fix/7-foo-..-bar", "not a valid branch name")

    monkeypatch.setattr(worktree_add, "ensure_worktree", boom)
    code = worktree_add.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "owner/repo",
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
        if argv[1:4] == ["worktree", "list", "--porcelain"]:
            clone = Path(spec.cwd).resolve()
            return _result(
                argv,
                stdout=f"worktree {clone}\0HEAD dddddddddddddddddddddddddddddddddddddddd\0branch refs/heads/main\0\0",
            )
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
    assert any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)
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
    assert any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)
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
    assert any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)
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
    assert any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)
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
    assert any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)


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
    assert not any(call[1:4] == ["worktree", "remove", "--force"] for call in runner.calls)


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
    out = remove_worktree(runner, clone, missing)
    assert out == {"ok": True, "removed": False, "already_gone": True}
    assert not any(call[1] == "worktree" for call in runner.calls)



def test_remove_worktree_uses_rmtree_only_after_git_and_registry_confirm(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "corner"
    corner.mkdir()
    class _Registry(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["worktree", "list", "--porcelain"]:
                self.calls.append(argv)
                return _result(
                    argv,
                    stdout=f"worktree {clone}\0HEAD dddddddddddddddddddddddddddddddddddddddd\0branch refs/heads/main\0\0",
                )
            return super().run(spec, live=live)

    runner = _Registry()

    out = remove_worktree(runner, clone, corner)

    assert out == {"ok": True, "removed": True}
    assert not corner.exists()
    assert any(call[1:4] == ["worktree", "list", "--porcelain"] for call in runner.calls)
    assert any(call[1:3] == ["worktree", "prune"] for call in runner.calls)


def test_remove_worktree_keeps_path_when_git_refuses_remove(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    corner = tmp_path / "foreign"
    corner.mkdir()

    class _Refuses(_ResetRunner):
        def run(self, spec, *, live):
            argv = list(spec.argv)
            self.calls.append(argv)
            if argv[1:4] == ["worktree", "remove", "--force"]:
                return _result(argv, returncode=128, stderr="fatal: not a working tree")
            return _result(argv)

    runner = _Refuses()
    out = remove_worktree(runner, clone, corner)

    assert out["ok"] is False
    assert "not a working tree" in out["error"]
    assert corner.is_dir()
    assert not any(call[1:3] == ["worktree", "list"] for call in runner.calls)


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
    out = remove_worktree(runner, clone, corner)

    assert out == {"ok": False, "removed": False, "error": "git still owns worktree after removal"}
    assert corner.is_dir()
    assert not any(call[1:3] == ["worktree", "prune"] for call in runner.calls)


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

    out = remove_worktree(_EmptyRegistry(), clone, corner)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership after git removal",
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

    out = remove_worktree(_TruncatedRegistry(), clone, corner)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership after git removal",
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
    out = remove_worktree(runner, clone, corner)

    assert out == {
        "ok": False,
        "removed": False,
        "error": "cannot confirm worktree ownership after git removal",
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

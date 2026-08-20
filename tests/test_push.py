from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace


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


def _reject_token_mismatch(**_kwargs) -> None:
    raise RuntimeError("preflight failed; live mutation blocked (lease=token_mismatch)")


def test_push_token_mismatch_pushes_verified_issue_branch(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from lokay.proc import push_branch as push_module

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    clone = tmp_path / "clone"
    _init_repo(clone)
    _git(clone, "remote", "add", "origin", str(origin))
    source = clone / "src.py"
    source.write_text("base\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "-m", "base")
    _git(clone, "push", "-u", "origin", "main")

    worktree = tmp_path / "issue-worktree"
    branch = "ai/fix/393"
    _git(clone, "worktree", "add", "-b", branch, str(worktree))
    (worktree / "src.py").write_text("on goal\n", encoding="utf-8")
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", "fix #393")
    head = _git(worktree, "rev-parse", "HEAD").strip()

    cfg = SimpleNamespace(repos=[SimpleNamespace(clone_path=clone)])
    monkeypatch.setattr(push_module, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(push_module, "mutations_allowed", _reject_token_mismatch)

    assert push_module.main(
        ["--live", "--repo", "mikolaj92/lokay", "--worktree", str(worktree), "--branch", branch]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert _git(origin, "rev-parse", f"refs/heads/{branch}").strip() == head


def test_push_token_mismatch_still_refuses_configured_main(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from lokay.proc import push_branch as push_module

    clone = tmp_path / "clone"
    _init_repo(clone)
    cfg = SimpleNamespace(repos=[SimpleNamespace(clone_path=clone)])
    monkeypatch.setattr(push_module, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(push_module, "mutations_allowed", _reject_token_mismatch)

    assert push_module.main(
        ["--live", "--repo", "mikolaj92/lokay", "--worktree", str(clone), "--branch", "main"]
    ) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "token_mismatch" in payload["error"]


def test_push_token_mismatch_refuses_branch_other_than_worktree_head(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from lokay.proc import push_branch as push_module

    clone = tmp_path / "clone"
    _init_repo(clone)
    source = clone / "src.py"
    source.write_text("base\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "-m", "base")
    worktree = tmp_path / "issue-worktree"
    _git(clone, "worktree", "add", "-b", "ai/fix/393", str(worktree))

    cfg = SimpleNamespace(repos=[SimpleNamespace(clone_path=clone)])
    monkeypatch.setattr(push_module, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(push_module, "mutations_allowed", _reject_token_mismatch)

    assert push_module.main(
        ["--live", "--repo", "mikolaj92/lokay", "--worktree", str(worktree), "--branch", "other"]
    ) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False

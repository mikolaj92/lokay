from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace


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




def test_commit_all_cli_still_commits_lokay(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from lokay.proc import commit_all as commit_module

    sentinel_runner = object()
    calls = []
    monkeypatch.setattr(commit_module, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(commit_module, "mutations_allowed", lambda **_kwargs: False)

    def record_commit(run, worktree, message, *, live, protected_checkouts):
        calls.append((run, worktree, message, live, tuple(protected_checkouts)))
        return False

    monkeypatch.setattr(commit_module, "commit_all", record_commit)

    assert commit_module.main(
        [
            "--repo",
            "mikolaj92/lokay",
            "--worktree",
            str(tmp_path),
            "--message",
            "keep working",
        ]
    ) == 0

    assert calls == [(sentinel_runner, tmp_path, "keep working", False, ())]
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["committed"] is False
    assert payload.get("skipped") is None


def test_commit_all_refuses_configured_checkout_on_main(tmp_path: Path) -> None:
    repo = tmp_path / "lokay-checkout"
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


def test_commit_all_token_mismatch_commits_verified_issue_worktree(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from lokay.proc import commit_all as commit_module

    clone = tmp_path / "clone"
    worktree = tmp_path / "issue-worktree"
    _init_repo(clone)
    source = clone / "src" / "foo.py"
    source.parent.mkdir()
    source.write_text("base\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "-m", "base")
    _git(clone, "worktree", "add", "-b", "ai/fix/380", str(worktree))
    source = worktree / "src" / "foo.py"
    source.write_text("on goal\n", encoding="utf-8")
    before = _git(worktree, "rev-parse", "HEAD").strip()

    cfg = SimpleNamespace(repos=[SimpleNamespace(clone_path=clone)])
    monkeypatch.setattr(commit_module, "load_cfg", lambda _args: cfg)

    def reject_lease(**_kwargs):
        raise RuntimeError("preflight failed; live mutation blocked (lease=token_mismatch)")

    monkeypatch.setattr(commit_module, "mutations_allowed", reject_lease)

    assert commit_module.main(
        ["--live", "--worktree", str(worktree), "--message", "fix #380"]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["committed"] is True
    assert _git(worktree, "rev-parse", "HEAD").strip() != before
    assert _git(worktree, "show", "HEAD:src/foo.py") == "on goal\n"


def test_commit_all_token_mismatch_still_refuses_configured_main(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from lokay.proc import commit_all as commit_module

    clone = tmp_path / "clone"
    _init_repo(clone)
    source = clone / "src" / "foo.py"
    source.parent.mkdir()
    source.write_text("base\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "-m", "base")
    source.write_text("dirty\n", encoding="utf-8")
    before = _git(clone, "rev-parse", "HEAD").strip()

    cfg = SimpleNamespace(repos=[SimpleNamespace(clone_path=clone)])
    monkeypatch.setattr(commit_module, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        commit_module,
        "mutations_allowed",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("preflight failed; live mutation blocked (lease=token_mismatch)")
        ),
    )

    assert commit_module.main(
        ["--live", "--worktree", str(clone), "--message", "must refuse"]
    ) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert _git(clone, "rev-parse", "HEAD").strip() == before
    assert _git(clone, "status", "--short").splitlines() == [" M src/foo.py"]


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

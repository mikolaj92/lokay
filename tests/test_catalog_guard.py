"""Hermetic tests for lokay.proc.catalog_guard (tmp git repo)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from lokay.proc import catalog_guard

CATALOG = "repos.mikolaj92.yaml"


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t.test",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _init_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "lokay"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "t")
    catalog = repo / CATALOG
    catalog.write_text("repos: []\n", encoding="utf-8")
    _git(repo, "add", CATALOG)
    _git(repo, "commit", "-m", "catalog")
    return repo, catalog


def test_save_without_skip_worktree_is_unprotected(tmp_path: Path, capsys):
    repo, catalog = _init_repo(tmp_path)
    code = catalog_guard.main(["--repo-root", str(repo), "--save"])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["protected"] is False
    assert payload["path"] == str(catalog.resolve())
    git_dir = Path(_git(repo, "rev-parse", "--git-dir").stdout.strip())
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    assert not (git_dir / "lokay-catalog-guard" / CATALOG).exists()


def test_save_skip_worktree_copies_aside_and_restore_after_ff(tmp_path: Path, capsys):
    repo, catalog = _init_repo(tmp_path)
    catalog.write_text("local: true\n", encoding="utf-8")
    _git(repo, "update-index", "--skip-worktree", CATALOG)
    tag = _git(repo, "ls-files", "-v", "--", CATALOG).stdout.strip()
    assert tag.startswith("S")

    code = catalog_guard.main(["--repo-root", str(repo), "--save"])
    assert code == 0
    saved = _payload(capsys)
    assert saved["ok"] is True
    assert saved["protected"] is True
    assert saved["path"] == str(catalog.resolve())

    catalog.write_text("upstream: true\n", encoding="utf-8")
    code = catalog_guard.main(["--repo-root", str(repo), "--restore"])
    assert code == 0
    restored = _payload(capsys)
    assert restored["ok"] is True
    assert restored["protected"] is True
    assert restored["path"] == str(catalog.resolve())
    assert catalog.read_text(encoding="utf-8") == "local: true\n"


def test_assume_skip_worktree_saves_without_git_bit(tmp_path: Path, capsys):
    repo, catalog = _init_repo(tmp_path)
    catalog.write_text("local-assume\n", encoding="utf-8")
    tag = _git(repo, "ls-files", "-v", "--", CATALOG).stdout.strip()
    assert tag.startswith("H")

    code = catalog_guard.main(
        ["--repo-root", str(repo), "--save", "--assume-skip-worktree"]
    )
    assert code == 0
    saved = _payload(capsys)
    assert saved["protected"] is True

    catalog.write_text("clobbered\n", encoding="utf-8")
    code = catalog_guard.main(["--repo-root", str(repo), "--restore"])
    assert code == 0
    restored = _payload(capsys)
    assert restored["protected"] is True
    assert catalog.read_text(encoding="utf-8") == "local-assume\n"


def test_restore_without_aside_is_unprotected(tmp_path: Path, capsys):
    repo, catalog = _init_repo(tmp_path)
    code = catalog_guard.main(["--repo-root", str(repo), "--restore"])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["protected"] is False
    assert payload["path"] == str(catalog.resolve())


def test_restore_fail_closed_when_cannot_write(tmp_path: Path, capsys):
    repo, catalog = _init_repo(tmp_path)
    catalog.write_text("keep-me\n", encoding="utf-8")
    _git(repo, "update-index", "--skip-worktree", CATALOG)
    assert catalog_guard.main(["--repo-root", str(repo), "--save"]) == 0
    _payload(capsys)

    catalog.unlink()
    catalog.mkdir()
    code = catalog_guard.main(["--repo-root", str(repo), "--restore"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "cannot write" in payload["error"]
    assert payload["protected"] is True
    assert payload["path"] == str(catalog.resolve())
    git_dir = Path(_git(repo, "rev-parse", "--git-dir").stdout.strip())
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    aside = git_dir / "lokay-catalog-guard" / CATALOG
    assert aside.is_file()
    assert aside.read_text(encoding="utf-8") == "keep-me\n"


def test_missing_repo_root_fails(tmp_path: Path, capsys):
    missing = tmp_path / "absent"
    code = catalog_guard.main(["--repo-root", str(missing), "--save"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "not a directory" in payload["error"]

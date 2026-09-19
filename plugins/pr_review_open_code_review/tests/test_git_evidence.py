from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
import sys
sys.path.insert(0, str(PACKAGE_SRC))

from lokay_review_open_code_review.git_evidence import verify_checkout  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _repo(tmp_path: Path) -> tuple[Path, str, str, dict]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "Review Test")
    _git(repo, "config", "user.email", "review@example.test")
    (repo / "file.py").write_text("value = 1\n")
    _git(repo, "add", "file.py")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "remote", "add", "origin", "https://github.com/acme/demo.git")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "file.py").write_text("value = 2\n")
    _git(repo, "commit", "-qam", "head")
    head = _git(repo, "rev-parse", "HEAD")
    patch = subprocess.check_output([
        "git", "-C", str(repo), "diff", "--binary", "--full-index",
        "--no-ext-diff", "--no-textconv", "--find-renames", "--no-color", base, head, "--",
    ])
    request = {
        "repo": "acme/demo",
        "head_repo": "acme/demo",
        "repo_path": str(repo),
        "head_sha": head,
        "base_ref_sha": base,
        "comparison_base_sha": base,
        "diff_sha256": hashlib.sha256(patch).hexdigest(),
        "diff_paths": [{"path": "file.py", "old_path": "", "status": "modified"}],
        "changed_ranges": {"file.py": [[1, 1]]},
    }
    return repo, base, head, request


def test_git_binary_uses_a_real_toolchain_binary_instead_of_the_xcrun_shim(monkeypatch):
    from lokay_review_open_code_review import git_evidence

    calls = []
    monkeypatch.setattr(
        git_evidence.shutil, "which",
        lambda name, path: calls.append((name, path)) or "/usr/bin/git",
    )
    monkeypatch.setattr(git_evidence.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(git_evidence.os, "access", lambda _path, _mode: True)

    assert git_evidence._git_binary() == git_evidence._FALLBACK_GIT
    assert git_evidence._git_runtime_paths(git_evidence._FALLBACK_GIT) == (
        Path("/Library/Developer/CommandLineTools"),
    )
    assert calls == [("git", "/usr/bin:/bin")]


def test_git_binary_uses_fallback_when_restricted_path_has_no_git(monkeypatch):
    from lokay_review_open_code_review import git_evidence

    monkeypatch.setattr(git_evidence.shutil, "which", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(git_evidence.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(git_evidence.os, "access", lambda _path, _mode: True)

    assert git_evidence._git_binary() == git_evidence._FALLBACK_GIT


def test_local_path_origin_is_not_canonical_github_identity(tmp_path: Path):
    repo, _base, _head, request = _repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", str(repo)], check=True)
    with pytest.raises(ValueError, match="origin"):
        verify_checkout(request)


def test_exact_local_checkout_evidence_matches_request(tmp_path: Path):
    _repo_path, _base, _head, request = _repo(tmp_path)

    observed = verify_checkout(request)

    assert observed["head_sha"] == request["head_sha"]
    assert observed["comparison_base_sha"] == request["comparison_base_sha"]
    assert observed["diff_sha256"] == request["diff_sha256"]
    assert observed["diff_paths"] == request["diff_paths"]
    assert observed["changed_ranges"] == {"file.py": [(1, 1)]}


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ("head", "HEAD"),
        ("patch", "patch digest"),
        ("inventory", "path inventory"),
        ("ranges", "changed-line ranges"),
        ("dirty", "clean"),
    ],
)
def test_checkout_drift_fails_closed(tmp_path: Path, change: str, error: str):
    repo, _base, _head, request = _repo(tmp_path)
    if change == "head":
        request["head_sha"] = "0" * 40
    elif change == "patch":
        request["diff_sha256"] = "0" * 64
    elif change == "inventory":
        request["diff_paths"] = [{"path": "other.py", "old_path": "", "status": "modified"}]
    elif change == "ranges":
        request["changed_ranges"] = {"file.py": [[1, 2]]}
    elif change == "dirty":
        (repo / "untracked.txt").write_text("unexpected")
    with pytest.raises(ValueError, match=error):
        verify_checkout(request)

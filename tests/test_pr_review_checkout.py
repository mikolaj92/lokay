from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from lokay.config import Config, RepoConfig
from lokay.pr_review_checkout import prepare_review_checkout, verify_review_checkout_unchanged
from lokay.runner import Runner


def _repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    source = tmp_path / "origin"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True)
    (source / "file.py").write_text("value = 1\n")
    subprocess.run(["git", "-C", str(source), "add", "file.py"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "base"], check=True)
    base = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    (source / "file.py").write_text("value = 2\n")
    subprocess.run(["git", "-C", str(source), "commit", "-qam", "head"], check=True)
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--no-local", str(source), str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin", "https://github.com/acme/demo.git"], check=True)
    for sha in (base, head):
        subprocess.run(["git", "-C", str(clone), "cat-file", "-e", sha], check=True)
    return source, clone, base, head


def test_prepare_review_checkout_pins_head_and_hashes_exact_patch(tmp_path: Path, monkeypatch):
    _source, clone, base, head = _repo(tmp_path)
    artifacts = tmp_path / "artifacts"
    # GitHub is intentionally not contacted: both exact objects are already local.
    monkeypatch.setattr("lokay.pr_review_checkout._origin_for_repo", lambda _repo: str(_source))
    monkeypatch.setattr(
        "lokay.pr_review_checkout._verify_origin",
        lambda *_args: "https://github.com/acme/demo.git",
    )
    cfg = Config(
        repos=[RepoConfig(name="acme/demo", clone_path=clone)],
        pr_review_artifacts_dir=artifacts,
    )
    class LocalFetchRunner:
        def __init__(self):
            self.delegate = Runner()

        def run(self, spec, *, live):
            return self.delegate.run(spec, live=live)

    review = prepare_review_checkout(cfg, LocalFetchRunner(), "acme/demo", base, head, live=True)

    assert review.path != clone
    assert review.comparison_base_sha == base
    assert review.diff_paths == [{"path": "file.py", "old_path": "", "status": "modified"}]
    assert review.changed_ranges == {"file.py": [(1, 1)]}
    patch = subprocess.check_output([
        "git", "-C", str(review.path), "diff", "--binary", "--full-index",
        "--no-ext-diff", "--no-textconv", "--find-renames", "--no-color", base, head, "--",
    ])
    assert review.diff_sha256 == hashlib.sha256(patch).hexdigest()
    assert review.patch == patch
    verify_review_checkout_unchanged(Runner(), review, head_sha=head)
    from lokay.pr_review_checkout import recompute_review_evidence
    recompute_review_evidence(Runner(), review, base_ref_sha=base, head_sha=head)

    # Fala serializes tuple ranges as JSON arrays before the boundary receives
    # them again during revalidation.
    round_tripped = replace(review, changed_ranges=json.loads(json.dumps(review.changed_ranges)))
    recompute_review_evidence(Runner(), round_tripped, base_ref_sha=base, head_sha=head)

    (review.path / "injected.txt").write_text("repo write")
    with pytest.raises(ValueError, match="changed during review"):
        verify_review_checkout_unchanged(Runner(), review, head_sha=head)


def test_prepare_review_checkout_fetches_exact_fork_head_from_validated_head_repository(tmp_path: Path, monkeypatch):
    _source, clone, base, head = _repo(tmp_path)
    fork = tmp_path / "fork"
    subprocess.run(["git", "clone", "-q", "--no-local", str(_source), str(fork)], check=True)
    subprocess.run(["git", "-C", str(fork), "checkout", "-q", "--detach", base], check=True)
    (fork / "file.py").write_text("value = 3\n")
    subprocess.run(["git", "-C", str(fork), "add", "file.py"], check=True)
    subprocess.run(["git", "-C", str(fork), "config", "user.name", "Fork Test"], check=True)
    subprocess.run(["git", "-C", str(fork), "config", "user.email", "fork@example.com"], check=True)
    subprocess.run(["git", "-C", str(fork), "commit", "-qm", "fork-only head"], check=True)
    fork_head = subprocess.check_output(["git", "-C", str(fork), "rev-parse", "HEAD"], text=True).strip()
    assert subprocess.run(["git", "-C", str(clone), "cat-file", "-e", fork_head], check=False).returncode != 0
    canonical_url = f"file://{_source}"
    fork_url = f"file://{fork}"
    monkeypatch.setattr(
        "lokay.pr_review_checkout._origin_for_repo",
        lambda name: canonical_url if name == "acme/demo" else fork_url,
    )
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin", canonical_url], check=True)
    branch = subprocess.check_output(["git", "-C", str(clone), "symbolic-ref", "--short", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--detach", base], check=True)
    subprocess.run(["git", "-C", str(clone), "branch", "-D", branch], check=True)
    subprocess.run(["git", "-C", str(clone), "update-ref", "-d", f"refs/remotes/origin/{branch}"], check=False)
    subprocess.run(["git", "-C", str(clone), "gc", "--prune=now"], check=True)
    cfg = Config(repos=[RepoConfig(name="acme/demo", clone_path=clone)], pr_review_artifacts_dir=tmp_path / "fork-artifacts")
    review = prepare_review_checkout(cfg, Runner(), "acme/demo", base, fork_head, live=True, head_repo="contributor/demo-fork")
    assert review.diff_paths == [{"path": "file.py", "old_path": "", "status": "modified"}]
    assert subprocess.check_output(
        ["git", "-C", str(review.path), "remote", "get-url", "origin"], text=True
    ).strip() == canonical_url


def test_fetch_source_follows_the_clone_credential_free_transport():
    from lokay.pr_review_checkout import _fetch_source_for

    ssh = "git@github.com:acme/demo.git"
    https = "https://github.com/acme/demo.git"
    assert _fetch_source_for("acme/demo", ssh) == ssh
    assert _fetch_source_for("contributor/fork", ssh) == "git@github.com:contributor/fork.git"
    assert _fetch_source_for("acme/demo", https) == https
    assert _fetch_source_for("contributor/fork", https) == "https://github.com/contributor/fork.git"


def test_prepare_review_checkout_snapshots_from_verified_clone_not_github_https(tmp_path: Path):
    """Live class: clone origin is SSH; inventing GitHub HTTPS prompts and cannot review."""
    _source, clone, base, head = _repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(clone), "remote", "set-url", "origin", "git@github.com:acme/demo.git"],
        check=True,
    )
    fetches: list[tuple[str, ...]] = []

    class Spy(Runner):
        def run(self, spec, *, live):
            argv = spec.argv
            if argv and argv[0] == "git" and "fetch" in argv:
                fetches.append(argv)
            return super().run(spec, live=live)

    cfg = Config(
        repos=[RepoConfig(name="acme/demo", clone_path=clone)],
        pr_review_artifacts_dir=tmp_path / "ssh-artifacts",
    )
    review = prepare_review_checkout(cfg, Spy(), "acme/demo", base, head, live=True)
    assert review.diff_paths == [{"path": "file.py", "old_path": "", "status": "modified"}]
    blob = " ".join(" ".join(part) for part in fetches)
    assert "https://github.com" not in blob
    assert "git@github.com" not in blob
    assert subprocess.check_output(
        ["git", "-C", str(review.path), "remote", "get-url", "origin"], text=True
    ).strip() == "git@github.com:acme/demo.git"


def test_verify_origin_accepts_the_canonical_ssh_transport(tmp_path: Path):
    _source, clone, _base, _head = _repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(clone), "remote", "set-url", "origin", "git@github.com:acme/demo.git"],
        check=True,
    )

    from lokay.pr_review_checkout import _verify_origin

    _verify_origin(Runner(), clone, "acme/demo")


def test_prepare_review_checkout_rejects_noncanonical_origin_and_sha(tmp_path: Path):
    _source, clone, base, head = _repo(tmp_path)
    cfg = Config(repos=[RepoConfig(name="acme/demo", clone_path=clone)], pr_review_artifacts_dir=tmp_path / "artifacts")
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin", "https://user:pass@github.com/acme/demo.git"], check=True)
    with pytest.raises(ValueError, match="origin"):
        prepare_review_checkout(cfg, Runner(), "acme/demo", base, head, live=True)

    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin", "https://github.com/acme/demo.git"], check=True)
    with pytest.raises(ValueError, match="SHAs"):
        prepare_review_checkout(cfg, Runner(), "acme/demo", "bad", head, live=True)

"""Build and verify an immutable, isolated GitHub PR review checkout."""

from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lokay.config import Config
from lokay.runner import Runner, git_spec

_SHA = re.compile(r"^[0-9a-f]{40}$")
_OWNER_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class ReviewCheckout:
    path: Path
    comparison_base_sha: str
    diff_sha256: str
    diff_paths: list[dict[str, str]]
    changed_ranges: dict[str, list[tuple[int, int]]]
    patch: bytes


def _run(runner: Runner, argv: list[str], cwd: Path, *, timeout: int = 120) -> str:
    result = runner.run(git_spec(argv, cwd=cwd, timeout_seconds=timeout), live=True)
    if result.returncode != 0 or (result.stderr or "").strip():
        detail = (result.stderr or result.stdout or "git command failed").strip()
        raise ValueError(f"review checkout git operation failed: {detail[:400]}")
    return result.stdout or ""


def _assert_commit(runner: Runner, path: Path, sha: str) -> None:
    if not _SHA.fullmatch(sha):
        raise ValueError("review checkout requires full immutable commit SHAs")
    actual = _run(runner, ["rev-parse", "--verify", f"{sha}^{{commit}}"], path).strip().lower()
    if actual != sha:
        raise ValueError("review checkout commit identity mismatch")


def _patch(runner: Runner, path: Path, base: str, head: str) -> bytes:
    result = runner.run(
        git_spec(
            ["diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
             "--find-renames", "--no-color", base, head, "--"],
            cwd=path,
            timeout_seconds=180,
        ),
        live=True,
    )
    if result.returncode != 0 or (result.stderr or "").strip():
        raise ValueError("cannot compute exact review patch")
    raw = (result.stdout or "").encode("utf-8")
    return raw


def _diff_paths(runner: Runner, path: Path, base: str, head: str) -> list[dict[str, str]]:
    raw = _run(
        runner,
        ["diff", "--name-status", "-z", "--find-renames", base, head, "--"],
        path,
    )
    fields = raw.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    rows: list[dict[str, str]] = []
    i = 0
    while i < len(fields):
        status = fields[i]
        i += 1
        if status.startswith(("R", "C")):
            if i + 1 >= len(fields):
                raise ValueError("truncated rename-aware Git diff inventory")
            old_path, new_path = fields[i], fields[i + 1]
            i += 2
            rows.append({"path": new_path, "old_path": old_path, "status": "renamed" if status.startswith("R") else "copied"})
            continue
        if i >= len(fields):
            raise ValueError("truncated Git diff inventory")
        rel = fields[i]
        i += 1
        kind = {"A": "added", "M": "modified", "D": "deleted", "T": "type_changed"}.get(status[:1])
        if kind is None:
            raise ValueError("unknown Git diff status")
        rows.append({"path": rel, "old_path": "", "status": kind})
    if len({(row["path"], row["old_path"]) for row in rows}) != len(rows):
        raise ValueError("ambiguous Git diff inventory")
    return rows


def _changed_ranges(runner: Runner, path: Path, base: str, head: str, paths: list[dict[str, str]]) -> dict[str, list[tuple[int, int]]]:
    raw = _run(
        runner,
        ["diff", "--unified=0", "--no-ext-diff", "--no-textconv", "--no-color", base, head, "--"],
        path,
    )
    ranges: dict[str, list[tuple[int, int]]] = {}
    current = ""
    for line in raw.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@") and current:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if not match:
                raise ValueError("malformed Git diff hunk header")
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            if count:
                ranges.setdefault(current, []).append((start, start + count - 1))
    allowed_paths = {row["path"] for row in paths if row["status"] != "deleted"}
    if set(ranges) - allowed_paths:
        raise ValueError("changed-line ranges do not match Git diff inventory")
    return ranges


def _changed_ranges_signature(value: Any) -> tuple[tuple[str, tuple[tuple[int, int], ...]], ...]:
    """Compare native and JSON-decoded changed-line ranges identically."""
    if not isinstance(value, dict):
        raise ValueError("malformed changed-line ranges")
    normalized: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    for path, ranges in value.items():
        if not isinstance(path, str) or not isinstance(ranges, (list, tuple)):
            raise ValueError("malformed changed-line ranges")
        parsed: list[tuple[int, int]] = []
        for item in ranges:
            if (
                not isinstance(item, (list, tuple))
                or len(item) != 2
                or any(not isinstance(number, int) or isinstance(number, bool) for number in item)
            ):
                raise ValueError("malformed changed-line ranges")
            parsed.append((item[0], item[1]))
        normalized.append((path, tuple(parsed)))
    return tuple(sorted(normalized))


def _origin_for_repo(repo: str) -> str:
    if not _OWNER_REPO.fullmatch(repo):
        raise ValueError("invalid GitHub repository name")
    return f"https://github.com/{repo}.git"


def _ssh_origin_for_repo(repo: str) -> str:
    if not _OWNER_REPO.fullmatch(repo):
        raise ValueError("invalid GitHub repository name")
    return f"git@github.com:{repo}.git"


def _fetch_source_for(repo: str, clone_origin: str) -> str:
    """GitHub fetch uses the clone's verified transport; never invent HTTPS over SSH."""
    if clone_origin.lower().startswith("git@github.com:"):
        return _ssh_origin_for_repo(repo)
    return _origin_for_repo(repo)


def _verify_origin(runner: Runner, clone: Path, repo: str) -> str:
    raw = _run(runner, ["remote", "get-url", "origin"], clone).strip().rstrip("/")
    expected = _origin_for_repo(repo).rstrip("/").lower()
    ssh = _ssh_origin_for_repo(repo).lower()
    # Accept the two credential-free GitHub transports used by Lokay's
    # authenticated Git carrier; reject credentials, alternate hosts, and local rewrites.
    if raw.lower() not in {expected, ssh}:
        raise ValueError("configured clone origin is not the canonical credential-free GitHub URL")
    return raw


def prepare_review_checkout(
    cfg: Config,
    runner: Runner,
    repo: str,
    base_ref_sha: str,
    head_sha: str,
    *,
    live: bool,
    head_repo: str = "",
) -> ReviewCheckout:
    if not live:
        raise ValueError("review checkout requires live Git evidence")
    if not _OWNER_REPO.fullmatch(repo):
        raise ValueError("invalid GitHub repository name")
    row = next((item for item in cfg.repos if item.name == repo), None)
    if row is None or not row.clone_path.is_dir():
        raise ValueError("configured repository clone is required for review")
    clone = row.clone_path.resolve()
    clone_origin = _verify_origin(runner, clone, repo)
    if head_repo and not _OWNER_REPO.fullmatch(head_repo):
        raise ValueError("invalid GitHub PR head repository name")
    if not _SHA.fullmatch(base_ref_sha) or not _SHA.fullmatch(head_sha):
        raise ValueError("review checkout requires full immutable commit SHAs")
    # GitHub is reached only from the verified clone, with that clone's
    # credential-free transport. Isolated checkout is a local snapshot.
    for sha, source_repo in ((base_ref_sha, repo), (head_sha, head_repo or repo)):
        try:
            _assert_commit(runner, clone, sha)
            continue
        except ValueError:
            pass
        source = _fetch_source_for(source_repo, clone_origin)
        fetched = runner.run(
            git_spec(
                ["fetch", "--quiet", "--no-tags", "--no-recurse-submodules", source, sha],
                cwd=clone,
                timeout_seconds=300,
            ),
            live=True,
        )
        if fetched.returncode != 0 or (fetched.stderr or "").strip():
            raise ValueError("cannot fetch exact PR commit from its validated repository")
        _assert_commit(runner, clone, sha)
    comparison = _run(runner, ["merge-base", base_ref_sha, head_sha], clone).strip().lower()
    if not _SHA.fullmatch(comparison):
        raise ValueError("cannot establish PR merge-base")

    root = cfg.pr_review_artifacts_dir / "checkouts"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    path = Path(tempfile.mkdtemp(prefix="review-", dir=root)).resolve()
    try:
        init = runner.run(git_spec(["init", "--quiet"], cwd=path), live=True)
        if init.returncode != 0:
            raise ValueError("cannot initialize isolated review checkout")
        _run(runner, ["remote", "add", "origin", str(clone)], path)
        _run(runner, ["fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", base_ref_sha], path, timeout=300)
        _run(runner, ["fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", head_sha], path, timeout=300)
        _assert_commit(runner, path, base_ref_sha)
        _assert_commit(runner, path, head_sha)
        _run(runner, ["checkout", "--quiet", "--detach", head_sha], path)
        actual = _run(runner, ["rev-parse", "HEAD"], path).strip().lower()
        if actual != head_sha:
            raise ValueError("isolated review checkout is not pinned to PR head")
        shallow = _run(runner, ["rev-parse", "--is-shallow-repository"], path).strip()
        if shallow != "false":
            raise ValueError("shallow review checkout cannot prove exact diff history")
        diff_paths = _diff_paths(runner, path, comparison, head_sha)
        if not diff_paths:
            raise ValueError("empty PR diff cannot be reviewed")
        patch = _patch(runner, path, comparison, head_sha)
        changed_ranges = _changed_ranges(runner, path, comparison, head_sha, diff_paths)
        return ReviewCheckout(
            path=path,
            comparison_base_sha=comparison,
            diff_sha256=hashlib.sha256(patch).hexdigest(),
            diff_paths=diff_paths,
            changed_ranges=changed_ranges,
            patch=patch,
        )
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        raise


def verify_review_checkout_unchanged(runner: Runner, checkout: ReviewCheckout, *, head_sha: str) -> None:
    if _run(runner, ["rev-parse", "HEAD"], checkout.path).strip().lower() != head_sha:
        raise ValueError("review checkout HEAD drifted")
    if _run(runner, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], checkout.path):
        raise ValueError("review checkout changed during review")


def recompute_review_evidence(
    runner: Runner, checkout: ReviewCheckout, *, base_ref_sha: str, head_sha: str
) -> None:
    _assert_commit(runner, checkout.path, base_ref_sha)
    _assert_commit(runner, checkout.path, head_sha)
    comparison = _run(
        runner, ["merge-base", base_ref_sha, head_sha], checkout.path
    ).strip().lower()
    if comparison != checkout.comparison_base_sha:
        raise ValueError("review merge-base drifted")
    paths = _diff_paths(runner, checkout.path, comparison, head_sha)
    patch = _patch(runner, checkout.path, comparison, head_sha)
    changed = _changed_ranges(runner, checkout.path, comparison, head_sha, paths)
    if paths != checkout.diff_paths:
        raise ValueError("review diff path inventory drifted")
    if hashlib.sha256(patch).hexdigest() != checkout.diff_sha256:
        raise ValueError("review patch digest drifted")
    if _changed_ranges_signature(changed) != _changed_ranges_signature(checkout.changed_ranges):
        raise ValueError("review changed-line ranges drifted")

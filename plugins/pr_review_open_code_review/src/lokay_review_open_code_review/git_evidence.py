"""Independent exact-checkout evidence checks (no Lokay imports)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

_SHA = re.compile(r"^[0-9a-f]{40}$")
_OWNER_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


_SHIM_GIT = "/usr/bin/git"
_FALLBACK_GIT = "/Library/Developer/CommandLineTools/usr/bin/git"


def _git_binary() -> str:
    candidate = shutil.which("git")
    resolved = str(Path(candidate).resolve()) if candidate else ""
    if not candidate or resolved == _SHIM_GIT:
        candidate = _FALLBACK_GIT
    if not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
        raise ValueError("trusted system git executable is unavailable")
    return candidate


def _git_runtime_paths(git_executable: str | Path) -> tuple[Path, ...]:
    """The Command Line Tools git needs its own tree. No Xcode beta path."""
    resolved = str(Path(git_executable).resolve())
    if resolved == _FALLBACK_GIT:
        return (Path("/Library/Developer/CommandLineTools"),)
    return ()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [_git_binary(), *args],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=60,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
             "HOME": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
    )
    if result.returncode or result.stderr:
        raise ValueError("could not verify immutable review checkout")
    return result.stdout


def _paths(repo: Path, base: str, head: str) -> list[dict[str, str]]:
    raw = _git(repo, "diff", "--name-status", "-z", "--find-renames", base, head, "--")
    fields = raw.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status.startswith("R"):
            if index + 1 >= len(fields):
                raise ValueError("malformed immutable diff inventory")
            old, new = fields[index], fields[index + 1]
            index += 2
            rows.append({"path": new, "old_path": old, "status": "renamed"})
        elif status.startswith("C"):
            if index + 1 >= len(fields):
                raise ValueError("malformed immutable diff inventory")
            old, new = fields[index], fields[index + 1]
            index += 2
            rows.append({"path": new, "old_path": old, "status": "copied"})
        else:
            if index >= len(fields):
                raise ValueError("malformed immutable diff inventory")
            path = fields[index]
            index += 1
            mapped = {"A": "added", "M": "modified", "D": "deleted", "T": "type_changed"}.get(status[:1])
            if mapped is None:
                raise ValueError("unknown immutable diff status")
            rows.append({"path": path, "old_path": "", "status": mapped})
    return rows


def _ranges(repo: Path, base: str, head: str, paths: list[dict[str, str]]) -> dict[str, list[tuple[int, int]]]:
    patch = _git(repo, "diff", "--unified=0", "--no-ext-diff", "--no-textconv", "--no-color", base, head, "--")
    result: dict[str, list[tuple[int, int]]] = {}
    path = ""
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("@@") and path:
            match = hunk.match(line)
            if not match:
                raise ValueError("malformed immutable diff hunk")
            start, count = int(match.group(1)), int(match.group(2) or "1")
            if count:
                result.setdefault(path, []).append((start, start + count - 1))
    allowed = {row["path"] for row in paths if row["status"] != "deleted"}
    if set(result) - allowed:
        raise ValueError("changed-line ranges do not match immutable path inventory")
    return result


def verify_checkout(request: Mapping[str, Any]) -> dict[str, Any]:
    repo_text = str(request.get("repo_path") or "")
    repo = Path(repo_text).resolve()
    if not repo.is_dir() or not _OWNER_REPO.fullmatch(str(request.get("repo") or "")):
        raise ValueError("isolated repository checkout and valid repo identity are required")
    origin = _git(repo, "remote", "get-url", "origin").strip().rstrip("/")
    expected_origin = f"https://github.com/{request['repo']}.git"
    expected_ssh_origin = f"git@github.com:{request['repo']}.git"
    head_repo = str(request.get("head_repo") or "")
    if not _OWNER_REPO.fullmatch(head_repo):
        raise ValueError("canonical PR head repository identity is required")
    if origin.lower() not in {expected_origin.lower(), expected_ssh_origin.lower()}:
        raise ValueError("review checkout origin does not match canonical GitHub repository")
    head = str(request.get("head_sha") or "").lower()
    base_ref = str(request.get("base_ref_sha") or "").lower()
    if not _SHA.fullmatch(head) or not _SHA.fullmatch(base_ref):
        raise ValueError("full immutable commit SHAs are required")
    actual_head = _git(repo, "rev-parse", "--verify", "HEAD").strip().lower()
    if actual_head != head:
        raise ValueError("review checkout HEAD does not match requested SHA")
    if _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise ValueError("review checkout must be clean and read-only")
    for sha in (head, base_ref):
        actual = _git(repo, "rev-parse", "--verify", f"{sha}^{{commit}}").strip().lower()
        if actual != sha:
            raise ValueError("review checkout is missing an exact immutable commit")
    comparison = _git(repo, "merge-base", base_ref, head).strip().lower()
    if comparison != str(request.get("comparison_base_sha") or "").lower():
        raise ValueError("review comparison base does not match immutable commits")
    paths = _paths(repo, comparison, head)
    if paths != list(request.get("diff_paths") or []):
        raise ValueError("review path inventory does not match immutable diff")
    patch = subprocess.run(
        [_git_binary(), "diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv", "--find-renames", "--no-color", comparison, head, "--"],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
             "HOME": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
    )
    if patch.returncode or patch.stderr:
        raise ValueError("could not compute immutable patch digest")
    digest = hashlib.sha256(patch.stdout).hexdigest()
    if digest != str(request.get("diff_sha256") or "").lower():
        raise ValueError("review patch digest does not match exact checkout")
    changed_ranges = _ranges(repo, comparison, head, paths)
    requested_ranges = {
        str(path): [(int(bounds[0]), int(bounds[1])) for bounds in rows]
        for path, rows in dict(request.get("changed_ranges") or {}).items()
    }
    if set(changed_ranges) != set(requested_ranges) or any(
        changed_ranges[path] != requested_ranges[path] for path in changed_ranges
    ):
        raise ValueError("review changed-line ranges do not match exact checkout")
    return {
        "head_repo": head_repo,
        "head_sha": head,
        "base_ref_sha": base_ref,
        "comparison_base_sha": comparison,
        "diff_sha256": digest,
        "diff_paths": paths,
        "changed_ranges": changed_ranges,
    }

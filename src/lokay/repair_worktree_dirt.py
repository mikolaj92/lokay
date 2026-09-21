"""Read-only repair admission: host evidence is not uncommitted product work."""
from __future__ import annotations

from pathlib import Path

from lokay.runner import Runner, git_spec

# Exact host-owned outputs excluded by localized implementation commits.
_EVIDENCE_PATHS = (".lokay/approach.md", ".lokay/localize.json")


def repair_worktree_dirt(runner: Runner, worktree: Path) -> str:
    """Return clean/evidence/product/unavailable; never change files or index."""
    status = runner.run(
        git_spec(
            ["--no-optional-locks", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=worktree, timeout_seconds=60,
        ),
        live=True,
    )
    if status.returncode != 0 or (status.stderr or "").strip():
        return "unavailable"
    raw = status.stdout or ""
    if not raw:
        return "clean"
    if not raw.endswith("\0"):
        return "unavailable"
    for record in raw[:-1].split("\0"):
        # Reject renames/copies outright (both endpoints matter), conflicts and
        # type changes. NUL records avoid quoting/newline/path-arrow ambiguity.
        if len(record) < 4 or record[2] != " ":
            return "unavailable"
        xy, path = record[:2], record[3:]
        if path not in _EVIDENCE_PATHS or not (
            xy == "??" or (xy != "  " and all(c in " MAD" for c in xy))
        ):
            return "product"
        target = worktree / path
        if target.is_symlink() or target.parent.is_symlink():
            return "product"

    # Working files can be regular while the staged version is a symlink.
    # Also inspect HEAD so deleted symlinks cannot masquerade as host evidence.
    for args in (
        ["ls-files", "--stage", "-z", "--", *_EVIDENCE_PATHS],
        ["ls-tree", "-z", "HEAD", "--", *_EVIDENCE_PATHS],
    ):
        result = runner.run(git_spec(args, cwd=worktree, timeout_seconds=30), live=True)
        if result.returncode != 0 or (result.stderr or "").strip():
            return "unavailable"
        entries = result.stdout or ""
        if entries and not entries.endswith("\0"):
            return "unavailable"
        for entry in entries.split("\0"):
            if not entry:
                continue
            metadata, sep, path = entry.partition("\t")
            fields = metadata.split()
            if not sep or len(fields) != 3:
                return "unavailable"
            if path not in _EVIDENCE_PATHS or fields[0] not in {"100644", "100755"}:
                return "product"
            if args[0] == "ls-files" and fields[2] != "0":
                return "product"
    return "evidence"

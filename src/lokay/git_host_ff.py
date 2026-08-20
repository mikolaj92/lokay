"""Fetch + fast-forward the mill host checkout onto origin/main."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from lokay.runner import Runner, git_spec

CANONICAL_REPO = "mikolaj92/lokay"
SKIP_WORKTREE_CATALOG = "repos.mikolaj92.yaml"


PROCESS_HEAD_ENV = "LOKAY_PROCESS_HEAD"


def checkout_head(checkout: Path) -> str:
    """Current HEAD of the mill checkout, or empty when unreadable."""
    try:
        out = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    return (out.stdout or "").strip()


def snapshot_process_head(checkout: Path) -> str:
    """Remember the HEAD this mill process imported. Empty if already set or unread."""
    existing = os.environ.get(PROCESS_HEAD_ENV, "").strip()
    if existing:
        return existing
    head = checkout_head(checkout)
    if head:
        os.environ[PROCESS_HEAD_ENV] = head
    return head


def process_head_moved(checkout: Path) -> dict[str, object] | None:
    """If launchd-ff moved HEAD under this live process, return a host_updated payload."""
    started = os.environ.get(PROCESS_HEAD_ENV, "").strip()
    if not started:
        return None
    current = checkout_head(checkout)
    if not current or current == started:
        return None
    return {
        "ok": False,
        "error": "host checkout moved under this process; restart required before product work",
        "reason": "host_updated",
        "health": "host_updated",
        "restart_required": True,
        "head": current,
        "origin_main": current,
        "process_head": started,
    }


def origin_is_lokay(url: str) -> bool:
    text = (url or "").strip().removesuffix(".git")
    if text.endswith(CANONICAL_REPO):
        return True
    return text in {
        f"https://github.com/{CANONICAL_REPO}",
        f"git@github.com:{CANONICAL_REPO}",
        f"ssh://git@github.com/{CANONICAL_REPO}",
    }


def skip_worktree_paths(runner: Runner, checkout: Path) -> list[str]:
    listed = runner.run(git_spec(["ls-files", "-v"], cwd=checkout), live=True)
    paths: list[str] = []
    for line in (listed.stdout or "").splitlines():
        if not line or line[0] not in {"S", "s"}:
            continue
        rel = line[1:].lstrip()
        if rel:
            paths.append(rel)
    return paths


def protected_skip_worktree_paths(skipped: list[str]) -> list[str]:
    """Only the host catalog is local. Product policy must follow origin/main."""
    return [rel for rel in skipped if rel == SKIP_WORKTREE_CATALOG]


def release_unprotected_skip_worktree(
    runner: Runner, checkout: Path, skipped: list[str], incoming: set[str]
) -> list[str]:
    """Drop skip-worktree on product files so mill policy can land."""
    released: list[str] = []
    for rel in skipped:
        if rel == SKIP_WORKTREE_CATALOG or rel not in incoming:
            continue
        runner.run_checked(
            git_spec(["update-index", "--no-skip-worktree", "--", rel], cwd=checkout),
            live=True,
        )
        released.append(rel)
    return released


def _rev_parse(runner: Runner, checkout: Path, ref: str) -> str:
    result = runner.run_checked(git_spec(["rev-parse", ref], cwd=checkout), live=True)
    return (result.stdout or "").strip()


def _dirty_entries(
    runner: Runner, checkout: Path, skipped: list[str]
) -> list[tuple[str, str]]:
    dirty = runner.run_checked(
        git_spec(
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=checkout,
        ),
        live=True,
    )
    entries: list[tuple[str, str]] = []
    skipped_set = set(skipped)
    fields = (dirty.stdout or "").split("\0")
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        status = field[:2]
        rel = field[3:] if len(field) > 3 else ""
        # In -z format a rename's destination is in this field and its source
        # follows as a second NUL-delimited field.
        if "R" in status or "C" in status:
            index += 1
        if rel and rel not in skipped_set:
            entries.append((status, rel))
    return entries


def _dirty_paths(runner: Runner, checkout: Path, skipped: list[str]) -> list[str]:
    return [rel for _status, rel in _dirty_entries(runner, checkout, skipped)]


def _is_harvest_leftover(status: str, rel: str) -> bool:
    """Changes a finished child may leave in the non-writing mill checkout."""
    if rel == ".lokay" or rel.startswith(".lokay/"):
        return True
    return status == "??" and (
        rel.startswith("src/") or rel.startswith("tests/")
    )


def _recover_harvest_checkout(
    runner: Runner, checkout: Path, skipped: list[str]
) -> bool:
    """Discard bounded harvest debris, but only in the primary host checkout."""
    # Linked issue worktrees have a .git file. They are writer-owned and must
    # never be repaired here, regardless of whether their receipt looks stale.
    git_dir = checkout / ".git"
    if not git_dir.is_dir() or git_dir.is_symlink():
        return False
    entries = _dirty_entries(runner, checkout, skipped)
    if not entries or not all(
        _is_harvest_leftover(status, rel) for status, rel in entries
    ):
        return False
    untracked = [rel for status, rel in entries if status == "??"]
    if untracked:
        runner.run_checked(
            git_spec(["clean", "-fd", "--", *untracked], cwd=checkout),
            live=True,
        )
    runner.run_checked(
        git_spec(["checkout", "-f", "main"], cwd=checkout), live=True
    )
    return True


def fast_forward_origin_main(runner: Runner, checkout: Path) -> dict[str, object]:
    """Fetch origin/main and fast-forward, or raise. Never reset --hard."""
    origin = runner.run_checked(
        git_spec(["remote", "get-url", "origin"], cwd=checkout), live=True
    ).stdout.strip()
    if not origin_is_lokay(origin):
        raise RuntimeError(f"refusing host-ff: origin is not {CANONICAL_REPO}")

    branch = runner.run_checked(
        git_spec(["rev-parse", "--abbrev-ref", "HEAD"], cwd=checkout), live=True
    ).stdout.strip()
    if branch != "main":
        skipped = skip_worktree_paths(runner, checkout)
        if _dirty_paths(runner, checkout, skipped):
            if not _recover_harvest_checkout(runner, checkout, skipped):
                raise RuntimeError("refusing host-ff: checkout is dirty")
        else:
            runner.run_checked(
                git_spec(["checkout", "main"], cwd=checkout), live=True
            )

    runner.run_checked(
        git_spec(["fetch", "origin", "main"], cwd=checkout, timeout_seconds=300),
        live=True,
    )
    head = _rev_parse(runner, checkout, "HEAD")
    remote = _rev_parse(runner, checkout, "origin/main")
    skipped = skip_worktree_paths(runner, checkout)
    if head == remote:
        return {
            "updated": False,
            "already_current": True,
            "head": head,
            "origin_main": remote,
            "skip_worktree": skipped,
        }

    ancestor = runner.run(
        git_spec(["merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=checkout),
        live=True,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("refusing host-ff: HEAD is not an ancestor of origin/main")

    if _dirty_paths(runner, checkout, skipped):
        raise RuntimeError("refusing host-ff: checkout is dirty")

    incoming = runner.run_checked(
        git_spec(["diff", "--name-only", "HEAD", "origin/main"], cwd=checkout),
        live=True,
    )
    incoming_paths = {
        line.strip() for line in (incoming.stdout or "").splitlines() if line.strip()
    }
    blocked = sorted(set(protected_skip_worktree_paths(skipped)) & incoming_paths)
    if blocked:
        raise RuntimeError(
            "refusing host-ff: origin/main would overwrite skip-worktree files: "
            + ", ".join(blocked)
        )
    released = release_unprotected_skip_worktree(
        runner, checkout, skipped, incoming_paths
    )
    skipped = [rel for rel in skipped if rel not in set(released)]

    runner.run_checked(
        git_spec(["merge", "--ff-only", "origin/main"], cwd=checkout, timeout_seconds=120),
        live=True,
    )
    new_head = _rev_parse(runner, checkout, "HEAD")
    if new_head != remote:
        raise RuntimeError("refusing host-ff: HEAD is still behind origin/main")

    # Re-assert skip-worktree so a merge cannot drop the host catalog bit.
    for rel in skipped:
        if (checkout / rel).exists():
            runner.run(
                git_spec(["update-index", "--skip-worktree", "--", rel], cwd=checkout),
                live=True,
            )
    return {
        "updated": True,
        "already_current": False,
        "head": new_head,
        "origin_main": remote,
        "skip_worktree": skipped,
    }

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


def _rev_parse(runner: Runner, checkout: Path, ref: str) -> str:
    result = runner.run_checked(git_spec(["rev-parse", ref], cwd=checkout), live=True)
    return (result.stdout or "").strip()


def _dirty_paths(runner: Runner, checkout: Path, skipped: list[str]) -> list[str]:
    dirty = runner.run(
        git_spec(["status", "--porcelain"], cwd=checkout), live=True
    )
    paths: list[str] = []
    skipped_set = set(skipped)
    for line in (dirty.stdout or "").splitlines():
        rel = line[3:] if len(line) > 3 else ""
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[-1]
        rel = rel.strip()
        if rel and rel not in skipped_set:
            paths.append(rel)
    return paths


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
            raise RuntimeError("refusing host-ff: checkout is dirty")
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
    blocked = sorted(set(skipped) & incoming_paths)
    if blocked:
        raise RuntimeError(
            "refusing host-ff: origin/main would overwrite skip-worktree files: "
            + ", ".join(blocked)
        )

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

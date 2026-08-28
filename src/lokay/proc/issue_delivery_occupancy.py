"""Read, validate, and clear detached issue-delivery occupancy receipts."""

from __future__ import annotations
import json, os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from lokay.localize import localize_belongs_to_issue
from lokay.proc.issue_delivery_process import (
    coding_live_for_issue,
    is_live_issue_to_pr_pid,
    pid_is_alive,
)
from lokay.proc.issue_delivery_receipts import (
    _receipt_write_lock,
    _starting_receipt_state,
    issue_to_pr_receipt_path,
)
from lokay.proc import repo_mutex


def _is_cycle_start_metric(data: dict[str, Any], path: Path | None) -> bool:
    """Require the complete metric schema and its distinct filename."""
    repo = data.get("repo")
    issue = data.get("issue")
    started_ts = data.get("started_ts")
    if (
        not isinstance(repo, str)
        or repo.strip() != repo
        or repo.count("/") != 1
        or any(not part for part in repo.split("/"))
        or isinstance(issue, bool)
        or not isinstance(issue, int)
        or issue < 1
        or not isinstance(started_ts, str)
        or len(started_ts) != 20
    ):
        return False
    try:
        parsed_started_ts = datetime.strptime(started_ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    if parsed_started_ts.strftime("%Y-%m-%dT%H:%M:%SZ") != started_ts:
        return False
    owner, name = repo.split("/", 1)
    expected_name = f"{owner}__{name}__{issue}.json"
    return path is None or path.name == expected_name


def _has_issue_identity(data: dict[str, Any]) -> bool:
    try:
        issue = int(data.get("issue"))
    except (TypeError, ValueError):
        return False
    return isinstance(data.get("repo"), str) and bool(data["repo"]) and issue > 0


def _receipt_is_readable(data: Any, path: Path | None = None) -> bool:
    """Validate lifecycle state without misreading malformed JSON as a metric."""
    if not isinstance(data, dict):
        return False
    if data.get("starting") is True:
        # Starting records must identify their lane. A malformed lifecycle
        # reservation is uncertainty, not an idle cycle file. Legacy records
        # with a complete identity stay occupied but are never reclaimed.
        try:
            issue = int(data.get("issue"))
        except (TypeError, ValueError):
            return False
        if (
            not isinstance(data.get("launch_id"), str)
            or not data["launch_id"]
            or not isinstance(data.get("repo"), str)
            or not data["repo"]
            or issue < 1
        ):
            return False
        if "activation" not in data:
            return True
        return _starting_receipt_state(data) != "unknown"
    if "starting" in data:
        return False
    if "pid" not in data:
        # Failed/reaped receipts (ok=false + identity) are idle, not unknown.
        if data.get("ok") is False and _has_issue_identity(data):
            return True
        return _is_cycle_start_metric(data, path)
    try:
        pid = int(data["pid"])
    except (TypeError, ValueError):
        return False
    # pid 0 / negative is a finished or reclaimable receipt, not unknown.
    if pid <= 0:
        return _has_issue_identity(data)
    return _has_issue_identity(data) and (
        "launch_id" not in data
        or (isinstance(data["launch_id"], str) and bool(data["launch_id"]))
    )


def has_unreadable_issue_to_pr_receipts(cycle_dir: Path | None = None) -> bool:
    """Whether lifecycle state is unknown and destructive work must pause."""
    root = (
        Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    )
    try:
        with os.scandir(root) as entries:
            paths = sorted(
                (Path(entry.path) for entry in entries if entry.name.endswith(".json")),
                key=lambda path: path.name,
            )
    except FileNotFoundError:
        return False
    except OSError:
        return True
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return True
        if not _receipt_is_readable(data, path):
            return True
    return False


def _worktree_paths_for_live_receipt(repo: str, issue: int) -> list[Path]:
    """Worktree paths for this receipt issue, same lookup classify uses.

    Receipts are ``{repo, issue, pid}``. Paths come from
    ``iter_worktrees`` + ``issue_number_from_branch``.
    """
    from lokay.config import Config, RepoConfig
    from lokay.git_worktree import iter_worktrees
    from lokay.stuck import issue_number_from_branch

    cfg = Config()
    repo_cfg = RepoConfig(name=str(repo), clone_path=Path("."))
    found: list[Path] = []
    for path, branch in iter_worktrees(cfg, repo_cfg):
        numbered = issue_number_from_branch(
            branch, branch_prefix=cfg.branch_prefix
        )
        if numbered == issue:
            found.append(path)
    return found


def _worktree_for_live_receipt(repo: str, issue: int) -> Path | None:
    """Single worktree for this receipt, or ``None`` if zero or several.

    Zero matches means no live workspace (caller frees occupancy).
    Several matches stay unknown (fail-closed occupy).
    """
    found = _worktree_paths_for_live_receipt(repo, issue)
    if len(found) == 1:
        return found[0]
    return None


def live_issue_to_pr_receipts(
    cycle_dir: Path | None = None,
    *,
    pid_alive=None,
    issue_closed=None,
    worktree_for=None,
) -> list[dict[str, Any]]:
    """Live or launching receipts that must keep a repo occupied."""
    root = (
        Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    )
    check = pid_alive or is_live_issue_to_pr_pid
    closed = issue_closed or repo_mutex._issue_is_closed
    worktree = worktree_for or _worktree_for_live_receipt
    if not root.is_dir():
        return []
    live: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if not data.get("repo") or data.get("issue") is None:
            continue
        # A reservation remains occupancy until its matching PID receipt is
        # published. Pipe-gated reservations whose launcher died before
        # activation are inert and can be recovered by the next dispatcher.
        # Starting with zero worktree is a ghost start, not occupancy (#899).
        # Same lookup as live pid (#891): zero frees; several stay fail-closed.
        if data.get("starting") is True:
            if _starting_receipt_state(data) == "orphaned":
                continue
            try:
                issue = int(data["issue"])
            except (TypeError, ValueError):
                continue
            if worktree_for is None:
                matches = _worktree_paths_for_live_receipt(str(data["repo"]), issue)
                if len(matches) == 0:
                    continue
                wt_path = matches[0] if len(matches) == 1 else None
            else:
                wt_path = worktree(str(data["repo"]), issue)
            belongs = localize_belongs_to_issue(wt_path, issue)
            if belongs is False:
                continue
            live.append(data)
            continue
        if "pid" not in data:
            continue
        if data.get("reaped") is True:
            # Over-budget plan_only already left the slot. A sleeping pi
            # must not keep occupancy until exit.
            continue
        try:
            pid = int(data["pid"])
            issue = int(data["issue"])
        except (TypeError, ValueError):
            continue
        if not (check(pid) or coding_live_for_issue(issue)):
            continue
        # Same closed-issue fact as repo_mutex: a live i2pr pid does not
        # hold the repo once GitHub confirms CLOSED. Probe failure stays
        # occupied (fail-closed), matching mutex inspection.
        if closed(str(data["repo"]), issue):
            continue
        # Sibling of CLOSED: leftover / foreign localize.json does not
        # occupy. Zero worktrees for this issue also frees the slot (#891).
        # Unreadable localize or several matching worktrees stay occupied.
        if worktree_for is None:
            matches = _worktree_paths_for_live_receipt(str(data["repo"]), issue)
            if len(matches) == 0:
                continue
            wt_path = matches[0] if len(matches) == 1 else None
        else:
            wt_path = worktree(str(data["repo"]), issue)
        belongs = localize_belongs_to_issue(wt_path, issue)
        if belongs is False:
            continue
        live.append(data)
    return live


def clear_issue_to_pr_receipt(receipt: dict[str, Any]) -> bool:
    """Remove the receipt only if it still describes the observed worker."""
    try:
        path = issue_to_pr_receipt_path(str(receipt["repo"]), int(receipt["issue"]))
        with _receipt_write_lock(path):
            current = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                return False
            identity_keys = ("repo", "issue", "pid", "launch_id", "starting")
            if any(current.get(key) != receipt.get(key) for key in identity_keys):
                return False
            path.unlink()
    except (KeyError, OSError, TypeError, ValueError):
        return False
    return True


def clear_dead_issue_to_pr_receipts(
    repos: Iterable[str],
    cycle_dir: Path | None = None,
    *,
    pid_alive=None,
) -> list[dict[str, Any]]:
    """Remove finished issue-to-PR receipts after a repo's PR was merged.

    A receipt is the harvest record for a detached child, so only a receipt
    whose wrapper and issue coder are both gone is safe to remove. In
    particular, a dead wrapper does not prove that a still-running pi is
    finished; keep that receipt until the open issue's coder exits.
    """
    root = (
        Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    )
    repo_names = {str(repo) for repo in repos if str(repo)}
    check = pid_alive or is_live_issue_to_pr_pid
    if not repo_names or not root.is_dir():
        return []

    cleared: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            with _receipt_write_lock(path):
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("repo") not in repo_names:
                    continue
                # Metric receipts and pipe-gated reservations are not detached
                # child receipts. Leave them for their owning lifecycle atom.
                if data.get("starting") is True or "pid" not in data:
                    continue
                pid = int(data["pid"])
                issue = int(data["issue"])
                if pid > 0 and (check(pid) or coding_live_for_issue(issue)):
                    continue
                path.unlink()
                cleared.append(data)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            # A concurrent lifecycle transition or malformed receipt is not
            # evidence that a live worker is safe to remove.
            continue
    return cleared

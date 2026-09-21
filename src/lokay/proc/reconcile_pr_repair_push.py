"""Reconcile selected PR publication evidence without blocking unrelated PRs."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, ok

_RECEIPT_SCAN_MAX_BYTES = 1_048_576
_RECEIPT_COMPATIBILITY_MAX_BYTES = 16 * 1024 * 1024
from lokay.proc import pr_repair_push, pr_repair_receipts


def _receipt_identities(directory: Path) -> list[tuple[str, int]]:
    """Read receipt identities without letting stale terminal payloads block recovery."""
    if not directory.exists():
        return []
    rows: list[tuple[str, int]] = []
    for path in sorted(directory.glob("*.json")):
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("repair receipt file is invalid")
            if info.st_size > _RECEIPT_COMPATIBILITY_MAX_BYTES:
                raise ValueError("repair receipt file is invalid")
            if info.st_size > _RECEIPT_SCAN_MAX_BYTES:
                value = _read_oversized_terminal_receipt(stream)
            else:
                try:
                    value = json.load(stream)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("repair receipt is malformed") from exc
        if not isinstance(value, dict):
            raise ValueError("repair receipt must be an object")
        repo = str(value.get("repo") or "")
        try:
            pr = int(value.get("pr") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("repair receipt identity is malformed") from exc
        if not repo or pr <= 0 or path.name != pr_repair_receipts.receipt_path(repo, pr, state_dir=directory.parent).name:
            raise ValueError("repair receipt identity does not match its path")
        rows.append((repo, pr))
    return rows


def _read_oversized_terminal_receipt(stream: Any) -> dict[str, Any]:
    """Accept only a parked, terminal-only legacy receipt over the scan bound.

    Large pending intents or receipts with confirmed identity must still be
    rejected: those records can affect recovery and must remain fail-closed.
    The compatibility bound is finite so a hostile receipt cannot make this
    pre-scan consume unbounded memory.
    """
    try:
        payload = json.load(stream)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("repair receipt is malformed") from exc
    if not isinstance(payload, dict):
        raise ValueError("repair receipt must be an object")
    allowed = {
        "repo", "pr", "attempts", "budget", "last_head_sha", "last_terminal",
        "updated_at", "parked",
    }
    if (
        set(payload) != allowed
        or payload.get("parked") is not True
        or payload.get("attempts") != payload.get("budget")
        or not isinstance(payload.get("last_terminal"), str)
        or payload.get("last_head_sha") != ""
    ):
        raise ValueError("repair receipt file is invalid")
    return payload


def reconcile_pending(
    *, config_path: str | None, live: bool,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Confirm pending attempts from exact live OPEN PR identities only.

    This is called from the parent PR-triage selector before the triage child is
    permitted to review or merge anything. Recovery is independent of whether
    the optional repair department is enabled.
    """
    state_dir = pr_repair_receipts.resolve_state_dir(config_path)
    if state_dir is None:
        return ok(route="fail_closed", reason="repair_push_state_directory_unavailable")
    selected = dict(selection or {})
    selected_route = str(selected.get("route") or "")
    selection_reason = str(selected.get("reason") or "")
    if selected_route == "pr" and (
        selected.get("ok") is not True
        or not str(selected.get("repo") or "").strip()
        or not str(selected.get("pr") or "").isdigit()
        or int(selected.get("pr") or 0) <= 0
        or not str(selected.get("branch") or "").strip()
    ):
        selected_route = "invalid"
    elif selected_route not in {"pr", "none"}:
        selected_route = "invalid"
    elif selected_route == "none" and selected.get("ok") is not True:
        selected_route = "invalid"
    budget = pr_repair_receipts.resolve_budget(config_path)
    recovered: list[dict[str, Any]] = []
    try:
        if selected_route == "pr":
            identities = [(str(selected["repo"]), int(selected["pr"]))]
            from lokay.proc.pr_repair_checkpoint import recover_legacy

            selected_path = pr_repair_receipts.receipt_path(*identities[0], state_dir=state_dir)
            if selected_path.exists() and selected_path.stat().st_size > _RECEIPT_COMPATIBILITY_MAX_BYTES:
                raise ValueError("selected repair receipt exceeds compatibility bound")
            current = pr_repair_receipts.read(*identities[0], state_dir=state_dir)
            # A confirmed checkpoint is historical evidence, not proof that a
            # later repair reached its own checkpoint before crashing. Discovery
            # still verifies exact lineage and archives the predecessor under lock.
            if live and not current.get("pending_push") and (
                not current.get("publication_checkpoint")
                or current.get("checkpoint_terminal") == "confirmed_target"
            ):
                legacy = recover_legacy(repo=identities[0][0], pr=identities[0][1],
                                        branch=str(selected["branch"]), state_dir=state_dir, budget=budget)
                if legacy.get("route") == "fail_closed":
                    return ok(**{k: v for k, v in legacy.items() if k != "ok"})
        else:
            identities = _receipt_identities(pr_repair_receipts.receipts_dir(state_dir=state_dir))
        for repo, pr in identities:
            if selected_route == "pr" and (repo, pr) != (
                str(selected["repo"]), int(selected["pr"])
            ):
                continue
            receipt = pr_repair_receipts.read(repo, pr, state_dir=state_dir)
            pending = receipt.get("pending_push") or (
                (receipt.get("publication_checkpoint") or {}).get("intent")
                if not receipt.get("checkpoint_terminal") else None
            )
            if pending is None:
                continue
            if selected_route == "pr" and selected["branch"] != pending["branch"]:
                return ok(route="fail_closed", reason="repair_push_selected_branch_mismatch", repo=repo, pr=pr)
            outcome = pr_repair_push.reconcile_pending_push(
                repo=repo, pr=pr, config_path=config_path, live=live,
                budget=budget, state_dir=state_dir,
            )
            if outcome.get("route") != "confirmed":
                return ok(
                    route="fail_closed",
                    reason=str(outcome.get("reason") or "repair_push_confirmation_failed"),
                    repo=repo, pr=pr,
                    recovery_case=str(outcome.get("recovery_case") or ""),
                    repair_push_intent_sha256=str(
                        pending.get("intent_sha256") or ""
                    ),
                    attempts=int(outcome.get("attempts") or receipt.get("attempts") or 0),
                    budget=int(outcome.get("budget") or receipt.get("budget") or budget),
                    recovered=recovered,
                )
            recovered.append({
                "repo": repo, "pr": pr,
                "branch": str(pending.get("branch") or ""),
                "head_sha": str(outcome.get("head_sha") or ""),
                "attempts": int(outcome.get("attempts") or 0),
                "parked": bool(outcome.get("parked")),
                "intent_sha256": str((receipt.get("pending_push") or {}).get("intent_sha256") or ""),
            })
    except (OSError, ValueError, TypeError):
        return ok(route="fail_closed", reason="pr_repair_receipt_invalid", recovered=recovered)
    if recovered:
        return ok(
            route="recovered", recovered=recovered, recovery_case="confirmed_target",
            **({"repair_push_intent_sha256": recovered[0]["intent_sha256"]} if len(recovered) == 1 else {}),
        )
    if selected_route == "invalid":
        return ok(
            route="fail_closed",
            reason=selection_reason or "pr_selection_invalid",
            recovered=[],
        )
    if selected_route == "pr":
        return ok(
            route="review",
            repo=str(selected["repo"]),
            pr=int(selected["pr"]),
            branch=str(selected["branch"]),
            recovered=[],
        )
    return ok(route="no_pr", recovered=[])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-reconcile-pr-repair-push")
    parser.add_argument("--config", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    return emit_exit(reconcile_pending(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())

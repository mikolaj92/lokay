"""Reconcile all durable PR-repair push intents before PR triage."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.proc import pr_repair_push, pr_repair_receipts


def _receipt_identities(directory: Path) -> list[tuple[str, int]]:
    """Read only enough of each receipt to discover its locked identity."""
    if not directory.exists():
        return []
    rows: list[tuple[str, int]] = []
    for path in sorted(directory.glob("*.json")):
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 1_048_576:
                raise ValueError("repair receipt file is invalid")
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
        identities = _receipt_identities(pr_repair_receipts.receipts_dir(state_dir=state_dir))
        for repo, pr in identities:
            receipt = pr_repair_receipts.read(repo, pr, state_dir=state_dir)
            if receipt.get("pending_push") is None:
                continue
            outcome = pr_repair_push.reconcile_pending_push(
                repo=repo, pr=pr, config_path=config_path, live=live,
                budget=budget, state_dir=state_dir,
            )
            if outcome.get("route") != "confirmed":
                return ok(
                    route="fail_closed",
                    reason=str(outcome.get("reason") or "repair_push_confirmation_failed"),
                    repo=repo, pr=pr,
                    repair_push_intent_sha256=str(
                        (receipt.get("pending_push") or {}).get("intent_sha256") or ""
                    ),
                    attempts=int(outcome.get("attempts") or receipt.get("attempts") or 0),
                    budget=int(outcome.get("budget") or receipt.get("budget") or budget),
                    recovered=recovered,
                )
            recovered.append({
                "repo": repo, "pr": pr,
                "branch": str(receipt["pending_push"].get("branch") or ""),
                "head_sha": str(outcome.get("head_sha") or ""),
                "attempts": int(outcome.get("attempts") or 0),
                "parked": bool(outcome.get("parked")),
                "intent_sha256": str((receipt.get("pending_push") or {}).get("intent_sha256") or ""),
            })
    except (OSError, ValueError, TypeError):
        return ok(route="fail_closed", reason="pr_repair_receipt_invalid", recovered=recovered)
    if recovered:
        return ok(
            route="recovered", recovered=recovered,
            **({"repair_push_intent_sha256": recovered[0]["intent_sha256"]} if len(recovered) == 1 else {}),
        )
    if selected_route == "invalid":
        return ok(
            route="fail_closed",
            reason=selection_reason or "pr_selection_invalid",
            recovered=[],
        )
    return ok(route="review" if selected_route == "pr" else "no_pr", recovered=[])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-reconcile-pr-repair-push")
    parser.add_argument("--config", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    return emit_exit(reconcile_pending(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())

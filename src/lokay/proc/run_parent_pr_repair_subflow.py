"""Parent NODE slot: invoke `pr_repair` after an authored sieve verdict."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.compose.pr_repair import compose_pr_repair
from lokay.proc import pr_repair_receipts


def _repair_meta(result: Mapping[str, Any] | None) -> tuple[str, str]:
    payload = dict(result or {})
    nested = payload.get("result")
    if isinstance(nested, Mapping):
        payload = {**payload, **dict(nested)}
    head = str(payload.get("head_sha") or "")
    terminal = str(
        payload.get("terminal") or payload.get("route") or payload.get("error") or ""
    )
    return head, terminal


def run(selected: dict[str, Any], *, config_path: str | None, live: bool) -> dict[str, Any]:
    budget = pr_repair_receipts.resolve_budget(config_path)
    state_dir = pr_repair_receipts.resolve_state_dir(config_path)
    result: dict[str, Any]
    try:
        result = compose_pr_repair(
            config_path=config_path,
            repo=str(selected["repo"]),
            pr_number=int(selected["pr"]),
            branch=str(selected["branch"]),
            review=dict(selected.get("review") or {}),
            live=live,
        )
    except Exception as exc:  # noqa: BLE001 — stamp then surface
        result = {"ok": False, "error": str(exc), "terminal": "compose_error"}
    nested = result.get("result") if isinstance(result.get("result"), Mapping) else {}
    skipped = bool(result.get("skipped") or (nested or {}).get("skipped"))
    if skipped:
        receipt = pr_repair_receipts.read(
            str(selected["repo"]),
            int(selected["pr"]),
            state_dir=state_dir,
        )
        return {
            "ok": True,
            "route": "skip",
            "reason": str(
                result.get("reason")
                or (nested or {}).get("reason")
                or "pr_already_merged"
            ),
            "repair": result,
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget),
            "parked": bool(receipt.get("parked")),
        }
    head_sha, terminal = _repair_meta(result)
    receipt = pr_repair_receipts.stamp(
        str(selected["repo"]),
        int(selected["pr"]),
        attempt_delta=1,
        head_sha=head_sha,
        terminal=terminal,
        budget=budget,
        state_dir=state_dir,
    )
    return {
        "ok": True,
        "route": "completed",
        "repair": result,
        "attempts": int(receipt.get("attempts") or 0),
        "budget": int(receipt.get("budget") or budget),
        "parked": bool(receipt.get("parked")),
    }

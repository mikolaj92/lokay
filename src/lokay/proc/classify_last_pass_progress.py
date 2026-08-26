"""Classify last-pass.json: repair only when the last pass did not move."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.pass_receipt import read_pass_receipt
from lokay.proc._common import add_config_live, load_cfg
from lokay.proc.survey_ttl import last_pass_is_empty_idle

_SOFT_HEALTH = frozenset(
    {
        "waiting",
        "repairing",
        "idle",
        "progress",
        "running",
        "offline",
        "overlap",
        "plateau",
        "host_updated",
        "pass_ceiling",
    }
)
_LEFTOVER_MARKERS = (
    "leftover_overflow",
    "leftover closeout catalog exceeds",
    "leftover closeout catalog exceeds authored slots",
)


def _remaining(receipt: dict[str, Any]) -> dict[str, Any]:
    rem = receipt.get("remaining")
    return rem if isinstance(rem, dict) else {}


def leftover_skip_signal(value: Any) -> bool:
    """True when leftover overflow / leftover skip is stamped anywhere."""
    if isinstance(value, dict):
        if value.get("leftover_skip") is True:
            return True
        reason = str(value.get("reason") or "")
        if reason == "leftover_overflow" or (
            value.get("skipped") and "leftover" in reason
        ):
            return True
        blob = " ".join(
            str(value.get(key) or "") for key in ("reason", "error", "note")
        ).lower()
        if any(marker in blob for marker in _LEFTOVER_MARKERS):
            return True
        leftover = value.get("leftover_closeout")
        if leftover is not None and leftover_skip_signal(leftover):
            return True
        return False
    if isinstance(value, str):
        low = value.lower()
        return any(marker in low for marker in _LEFTOVER_MARKERS)
    return False


def _empty_survey(receipt: dict[str, Any]) -> bool:
    if last_pass_is_empty_idle(receipt):
        return True
    return str(receipt.get("reason") or "").startswith("recent_empty_survey")


def _stale_receipt(receipt: dict[str, Any] | None) -> bool:
    if not isinstance(receipt, dict) or not receipt:
        return True
    kind = str(receipt.get("kind") or "")
    if kind and kind != "pass_receipt":
        return True
    if not receipt.get("ts"):
        return True
    return False


def _merged(receipt: dict[str, Any]) -> bool:
    if receipt.get("merged") is True:
        return True
    merged = receipt.get("merged_this_pass")
    if merged is True:
        return True
    if isinstance(merged, list) and merged:
        return True
    rem = _remaining(receipt)
    nested = rem.get("merged_this_pass")
    if nested is True or (isinstance(nested, list) and nested):
        return True
    for action in list(receipt.get("actions") or []):
        if not isinstance(action, dict):
            continue
        if action.get("merged") is True:
            return True
        if str(action.get("step") or "") == "pr_merge" and action.get("merged"):
            return True
    return False


def _new_pr(receipt: dict[str, Any]) -> bool:
    if receipt.get("new_pr") is True:
        return True
    rem = _remaining(receipt)
    if rem.get("new_pr") or rem.get("pr_created"):
        return True
    for action in list(receipt.get("actions") or []):
        if not isinstance(action, dict):
            continue
        step = str(action.get("step") or "")
        if step == "pr_create":
            return True
        if step == "issue_to_pr" and (
            action.get("pr") or action.get("pr_number") or action.get("url")
        ):
            return True
    return False


def moved_forward(receipt: dict[str, Any] | None) -> bool:
    """Moving forward is a new PR or a merge only."""
    if not isinstance(receipt, dict):
        return False
    return _new_pr(receipt) or _merged(receipt)


def _occupied(receipt: dict[str, Any]) -> bool:
    rem = _remaining(receipt)
    if int(rem.get("issue_to_pr_started") or 0) > 0:
        return True
    by_repo = rem.get("by_repo") or receipt.get("by_repo") or []
    return isinstance(by_repo, list) and any(
        isinstance(row, dict) and row.get("occupied") for row in by_repo
    )


def _factory(reason: str, *, moved: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "route": "factory",
        "reason": reason,
        "moved_forward": moved,
        "fingerprint": None,
        "evidence": "",
    }


def classify(receipt: dict[str, Any] | None) -> dict[str, Any]:
    """Route factory unless the last receipt did not move and is not excluded."""
    if _stale_receipt(receipt):
        return _factory("stale_receipt")
    assert isinstance(receipt, dict)
    if leftover_skip_signal(receipt):
        return _factory("leftover_skip")
    if _empty_survey(receipt):
        return _factory("empty_survey")
    if moved_forward(receipt):
        return _factory("moved_forward", moved=True)
    if _occupied(receipt):
        return _factory("occupied")
    health = str(receipt.get("health") or "")
    if health in _SOFT_HEALTH:
        return _factory(health or "soft_health")
    return {
        "ok": True,
        "route": "repair",
        "reason": "did_not_move",
        "moved_forward": False,
        "fingerprint": "did_not_move",
        "evidence": str(
            receipt.get("error") or receipt.get("health") or "last pass did not move"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-classify-last-pass-progress")
    add_config_live(parser)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    receipt = read_pass_receipt(state_path=cfg.state_path)
    return emit_exit(ok(**classify(receipt)))


if __name__ == "__main__":
    raise SystemExit(main())

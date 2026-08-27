"""Compose last_pass_moving + leftover_skip + receipt exclusions into one route."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.pass_receipt import read_pass_receipt
from lokay.proc._common import add_config_live, load_cfg
from lokay.proc.last_pass_moving import classify as classify_moving
from lokay.proc.leftover_skip import classify as classify_leftover
from lokay.proc.leftover_skip import leftover_skip_signal
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


def _remaining(receipt: dict[str, Any]) -> dict[str, Any]:
    rem = receipt.get("remaining")
    return rem if isinstance(rem, dict) else {}


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


def select(
    moving: dict[str, Any],
    leftover: dict[str, Any],
    receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    """Route factory unless the last receipt did not move and is not excluded."""
    if leftover.get("leftover_skip") or leftover_skip_signal(receipt):
        return _factory("leftover_skip")
    if _stale_receipt(receipt):
        return _factory("stale_receipt")
    assert isinstance(receipt, dict)
    if _empty_survey(receipt):
        return _factory("empty_survey")
    if moving.get("moved_forward"):
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


def classify(receipt: dict[str, Any] | None) -> dict[str, Any]:
    """Library compose of the two leaves. Fala runs the leaves as processes."""
    return select(classify_moving(receipt), classify_leftover(receipt), receipt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-select-repair-route")
    add_config_live(parser)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    receipt = read_pass_receipt(state_path=cfg.state_path)
    return emit_exit(ok(**classify(receipt)))


if __name__ == "__main__":
    raise SystemExit(main())

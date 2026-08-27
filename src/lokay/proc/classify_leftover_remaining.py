"""Leaf: leftover=0 with leftover inbox/ready is merge, not a cold wipe."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.pass_receipt import read_pass_receipt
from lokay.proc._common import add_config_live, load_cfg


def leftover_cleared(remaining: dict[str, Any] | None) -> bool:
    """True when leftover count is 0 or leftover_issues is empty."""
    if not isinstance(remaining, dict):
        return False
    if "leftover" in remaining:
        try:
            return int(remaining.get("leftover") or 0) == 0
        except (TypeError, ValueError):
            return False
    issues = remaining.get("leftover_issues")
    if issues is None:
        return False
    if isinstance(issues, (list, dict, tuple, set)):
        return len(issues) == 0
    return False


def remaining_has_inbox(remaining: dict[str, Any] | None) -> bool:
    """True when last-pass remaining still lists inbox, ready, or by_repo."""
    if not isinstance(remaining, dict):
        return False
    try:
        inbox = int(remaining.get("inbox") or 0)
    except (TypeError, ValueError):
        inbox = 0
    try:
        ready = int(remaining.get("ready") or 0)
    except (TypeError, ValueError):
        ready = 0
    if inbox > 0 or ready > 0:
        return True
    by_repo = remaining.get("by_repo")
    if isinstance(by_repo, list) and by_repo:
        return True
    if isinstance(by_repo, dict) and by_repo:
        return True
    return False


def classify(remaining: dict[str, Any] | None) -> dict[str, Any]:
    """route=merge when leftover is gone but inbox/ready/by_repo remain."""
    merge = leftover_cleared(remaining) and remaining_has_inbox(remaining)
    return {
        "ok": True,
        "route": "merge" if merge else "keep",
        "reason": "leftover_zero_has_remaining" if merge else "keep_remaining",
    }


def remaining_from_receipt(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(receipt, dict):
        return None
    remaining = receipt.get("remaining")
    return remaining if isinstance(remaining, dict) else None


def classify_receipt(receipt: dict[str, Any] | None) -> dict[str, Any]:
    return classify(remaining_from_receipt(receipt))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-classify-leftover-remaining")
    add_config_live(parser)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    receipt = read_pass_receipt(state_path=cfg.state_path)
    return emit_exit(ok(**classify_receipt(receipt)))


if __name__ == "__main__":
    raise SystemExit(main())

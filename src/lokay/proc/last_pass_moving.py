"""Leaf: last pass moved only when it published a new PR or merged."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.pass_receipt import read_pass_receipt
from lokay.proc._common import add_config_live, load_cfg


def _remaining(receipt: dict[str, Any]) -> dict[str, Any]:
    rem = receipt.get("remaining")
    return rem if isinstance(rem, dict) else {}


def _merged(receipt: dict[str, Any]) -> bool:
    if str(receipt.get("outcome") or "") == "merge":
        return True
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
    if str(receipt.get("outcome") or "") == "new_pr":
        return True
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


def classify(receipt: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        return {
            "ok": True,
            "moved_forward": False,
            "new_pr": False,
            "merged": False,
        }
    new_pr = _new_pr(receipt)
    merged = _merged(receipt)
    return {
        "ok": True,
        "moved_forward": new_pr or merged,
        "new_pr": new_pr,
        "merged": merged,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-last-pass-moving")
    add_config_live(parser)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    receipt = read_pass_receipt(state_path=cfg.state_path)
    return emit_exit(ok(**classify(receipt)))


if __name__ == "__main__":
    raise SystemExit(main())

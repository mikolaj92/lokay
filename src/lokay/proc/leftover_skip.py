"""Leaf: leftover overflow is not a stall and must not start repair."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.pass_receipt import read_pass_receipt
from lokay.proc._common import add_config_live, load_cfg

_LEFTOVER_MARKERS = (
    "leftover_overflow",
    "leftover closeout catalog exceeds",
    "leftover closeout catalog exceeds authored slots",
)


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


def classify(receipt: dict[str, Any] | None) -> dict[str, Any]:
    skipped = leftover_skip_signal(receipt)
    return {
        "ok": True,
        "leftover_skip": skipped,
        "reason": "leftover_skip" if skipped else "not_leftover",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-leftover-skip")
    add_config_live(parser)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    receipt = read_pass_receipt(state_path=cfg.state_path)
    return emit_exit(ok(**classify(receipt)))


if __name__ == "__main__":
    raise SystemExit(main())

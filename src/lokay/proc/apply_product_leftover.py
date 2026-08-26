"""Apply one leftover-closeout fact to one factory-pass envelope."""

from lokay.proc.leftover_skip import leftover_skip_signal


def apply(tick: dict, leftover: dict) -> dict:
    remaining = tick.get("remaining")
    if leftover_skip_signal(leftover):
        return {
            "ok": True,
            "tick": {
                **tick,
                "leftover_skip": True,
                "leftover_closeout": leftover,
                "reason": leftover.get("reason") or "leftover_overflow",
            },
        }
    if not leftover.get("labels_removed") or not isinstance(remaining, dict):
        return {"ok": True, "tick": tick}
    remaining = {**remaining, "issue_to_pr_started": 0}
    return {
        "ok": True,
        "tick": {
            **tick,
            "remaining": remaining,
            "progress": int(tick.get("progress") or 0)
            + int(leftover.get("leftover_closed") or 1),
            "leftover_closeout": leftover,
        },
    }

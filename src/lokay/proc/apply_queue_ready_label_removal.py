"""Remove ai:ready for one authoritative close outcome."""

from lokay.passkit.support import run_proc
from lokay.proc import label_issue


def apply(*, cfg_flags: list[str], live_flags: list[str], outcome: dict) -> dict:
    argv = [
        *cfg_flags,
        *live_flags,
        "--repo",
        str(outcome["repo"]),
        "--issue",
        str(outcome["issue"]),
        "--label",
        "ai:ready",
        "--remove",
    ]
    result = run_proc(label_issue.main, argv)
    return {
        "ok": bool(result.get("ok")),
        "applied": bool(result.get("applied")),
        "effect": result,
    }

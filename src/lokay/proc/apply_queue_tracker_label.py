"""Add ai:tracker for one authoritative tracker outcome."""

from lokay.passkit.support import run_proc
from lokay.proc import label_issue


def apply(*, cfg_flags: list[str], live_flags: list[str], outcome: dict) -> dict:
    result = run_proc(
        label_issue.main,
        [
            *cfg_flags,
            *live_flags,
            "--repo",
            str(outcome["repo"]),
            "--issue",
            str(outcome["issue"]),
            "--label",
            "ai:tracker",
        ],
    )
    return {
        "ok": bool(result.get("ok")),
        "applied": bool(result.get("applied")),
        "effect": result,
    }

"""Persist the pass counters after a blocked issue label attempt."""

from lokay.passkit import io as pass_io


def apply(*, pass_dir: str, failure: dict, label: dict) -> dict:
    if failure.get("route") != "blocked":
        return {"ok": True, "route": "done"}
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    applied = bool(label.get("applied"))
    working["blocked_this_pass"] = int(working.get("blocked_this_pass") or 0) + 1
    if applied:
        working["progress"] = int(working.get("progress") or 0) + 1
        working["remaining_ready"] = max(
            0, int(working.get("remaining_ready") or 0) - 1
        )
    working["actions"] = [
        *list(working.get("actions") or []),
        {"step": "label_blocked", **label},
    ]
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {
        "ok": True,
        "route": "park" if failure.get("plan_only") else "done",
        **failure,
    }

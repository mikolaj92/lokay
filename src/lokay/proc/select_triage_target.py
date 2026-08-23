"""Select at most one inbox triage target from the authored pass plan."""

from lokay.passkit import io as pass_io


def select(*, pass_dir: str) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    plan = pass_io.read_json(pass_io.plan_path(pass_dir))
    targets = list(plan.get("triage_targets") or [])
    if not begin.get("live") or not targets:
        return {"ok": True, "route": "none"}
    target = dict(targets[0])
    return {
        "ok": True,
        "route": "target",
        "repo": str(target["repo"]),
        "issue": int(target["issue"]),
    }

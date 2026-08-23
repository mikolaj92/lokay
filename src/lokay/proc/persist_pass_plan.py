"""Persist one already-reduced pass plan and its explanatory actions."""

from lokay.passkit import io as pass_io


def persist(*, pass_dir: str, reduced: dict) -> dict:
    plan = dict(reduced["plan"])
    pass_io.write_json(pass_io.plan_path(pass_dir), plan)
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    working["actions"] = list(reduced.get("actions") or [])
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "triage_count": len(plan["triage_targets"]),
        "closeout_count": len(plan["closeout_targets"]),
        "implement_candidate_count": len(plan["implement_candidates"]),
    }

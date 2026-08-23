"""Persist an explicit no-launch decision for a selected candidate."""

from lokay.passkit import io as pass_io


def apply(*, pass_dir: str, candidate: dict) -> dict:
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    working["actions"] = [
        *list(working.get("actions") or []),
        {
            "step": "keep_implementation_candidate",
            "repo": candidate.get("repo"),
            "issue": candidate.get("issue"),
            "reason": candidate.get("route") or candidate.get("error") or "unknown",
        },
    ]
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True, "applied": True, "route": "done"}

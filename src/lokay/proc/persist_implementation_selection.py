"""Persist one already-reduced implementation selection."""

from lokay.passkit import io as pass_io


def persist(*, pass_dir: str, reduced: dict) -> dict:
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    working.update(
        actions=list(reduced.get("actions") or []),
        ready_by_repo=dict(reduced.get("ready_by_repo") or {}),
        remaining_ready=int(reduced.get("remaining_ready") or 0),
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    payload = {
        "clean_repos": list(reduced.get("clean_repos") or []),
        "issue_budget": int(reduced.get("issue_budget") or 0),
    }
    if reduced.get("route") == "no_budget":
        payload["reason"] = "no_live_budget"
    pass_io.write_json(pass_io.implement_path(pass_dir), payload)
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "selected": len(payload["clean_repos"]),
        "issue_budget": payload["issue_budget"],
    }

"""Remove one no-longer-ready candidate from the pass snapshot."""

from lokay.passkit import io as pass_io


def apply(*, pass_dir: str, candidate: dict, gate: dict) -> dict:
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    repo = str(candidate["repo"])
    issue = int(candidate["issue"])
    ready = dict(working.get("ready_by_repo") or {})
    ready[repo] = [
        x for x in list(ready.get(repo) or []) if int(x.get("number", -1)) != issue
    ]
    working["ready_by_repo"] = ready
    working["remaining_ready"] = max(0, int(working.get("remaining_ready") or 0) - 1)
    working["actions"] = [
        *list(working.get("actions") or []),
        {"step": "verify_issue_ready", "repo": repo, "issue": issue, **gate},
    ]
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True, "route": "done", "dropped": True, "repo": repo, "issue": issue}

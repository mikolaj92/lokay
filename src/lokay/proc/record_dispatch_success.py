"""Persist one successful detached implementation launch."""

from lokay.passkit import io as pass_io
from lokay.stuck import clear_issue


def apply(*, pass_dir: str, launched: dict) -> dict:
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    repo = str(launched["repo"])
    issue = int(launched["issue"])
    result = dict(launched.get("launch") or {})
    ready = dict(working.get("ready_by_repo") or {})
    ready[repo] = [
        x for x in list(ready.get(repo) or []) if int(x.get("number", -1)) != issue
    ]
    stuck = dict(working.get("stuck") or {})
    clear_issue(stuck, repo, issue)
    working.update(
        ready_by_repo=ready,
        stuck=stuck,
        remaining_ready=max(0, int(working.get("remaining_ready") or 0) - 1),
        issue_to_pr_started=int(working.get("issue_to_pr_started") or 0) + 1,
        progress=int(working.get("progress") or 0) + 1,
    )
    working["actions"] = [
        *list(working.get("actions") or []),
        {"step": "issue_to_pr", "repo": repo, "issue": issue, **result},
    ]
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {
        "ok": True,
        "route": "receipt",
        "repo": repo,
        "issue": issue,
        "launch": result,
    }

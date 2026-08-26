"""Select at most one implementation candidate from the pass snapshot."""

from lokay.passkit import io as pass_io
from lokay.proc.catalog_work import work_by_repo
from lokay.proc.reduce_implementation_selection import parked_issue_keys
from lokay.stuck import excluded_numbers


def select(*, pass_dir: str) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    if not begin.get("live") or int(implement.get("issue_budget") or 0) <= 0:
        return {"ok": True, "route": "none", "reason": "no_live_budget"}
    stuck = dict(working.get("stuck") or begin.get("stuck") or {})
    parked = parked_issue_keys(working)
    ready = work_by_repo(
        working,
        stuck=stuck,
        branch_prefix=str(begin.get("branch_prefix") or "ai/fix/"),
    )
    for repo in list(implement.get("clean_repos") or []):
        excluded = excluded_numbers(stuck, str(repo))
        candidates = sorted(
            (
                x
                for x in list(ready.get(repo) or [])
                if int(x.get("number", -1)) not in excluded
                and (str(repo), int(x.get("number", -1))) not in parked
            ),
            key=lambda x: int(x.get("number", 0)),
        )
        if candidates:
            issue = dict(candidates[0])
            return {
                "ok": True,
                "route": "candidate",
                "repo": str(repo),
                "issue": int(issue["number"]),
                "title": str(issue.get("title") or ""),
                "candidate": issue,
            }
    return {"ok": True, "route": "none", "reason": "no_candidate"}

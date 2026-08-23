"""Persist one bounded implementation launch failure and select its Fala route."""

from lokay.passkit import io as pass_io
from lokay.stuck import record_failure


def apply(*, pass_dir: str, launched: dict) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    repo = str(launched["repo"])
    issue = int(launched["issue"])
    result = dict(launched.get("launch") or {})
    stuck = dict(working.get("stuck") or {})
    row = record_failure(
        stuck,
        repo=repo,
        number=issue,
        error=str(result.get("error") or result.get("fala") or "issue_to_pr failed"),
        max_failures=int(begin.get("max_fail") or 1),
    )
    if str(result.get("reason") or "") == "local_repair_exhausted":
        row["blocked"] = True
    working["stuck"] = stuck
    working["actions"] = [
        *list(working.get("actions") or []),
        {
            "step": "record_stuck",
            "repo": repo,
            "issue": issue,
            "failures": row.get("failures"),
            "blocked": bool(row.get("blocked")),
        },
    ]
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {
        "ok": True,
        "route": "blocked" if row.get("blocked") else "retry_later",
        "plan_only": str(result.get("error") or result.get("reason") or "")
        == "plan_only",
        "repo": repo,
        "issue": issue,
        "failure": result,
    }

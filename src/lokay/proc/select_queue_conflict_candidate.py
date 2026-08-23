"""Select at most one ready candidate for queue hygiene."""

from lokay.passkit import io as pass_io


def select(*, pass_dir: str) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    ready = dict(working.get("ready_by_repo") or {})
    for repo in list(implement.get("clean_repos") or []):
        rows = sorted(
            list(ready.get(repo) or []), key=lambda row: int(row.get("number") or 0)
        )
        if rows:
            issue = dict(rows[0])
            return {
                "ok": True,
                "route": "candidate",
                "repo": str(repo),
                "issue": int(issue["number"]),
                "candidate": issue,
            }
    return {"ok": True, "route": "none", "reason": "no_candidate"}

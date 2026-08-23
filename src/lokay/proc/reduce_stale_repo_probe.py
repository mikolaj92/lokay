"""Purely reduce the four explicit label probes for one repository."""


def reduce_state(selected: dict, rows: list[dict]) -> dict:
    if selected.get("route") != "repo":
        return {
            "ok": True,
            "route": selected.get("route", "empty"),
            "repo": selected.get("repo", ""),
        }
    failed = any(x.get("route") == "failed" for x in rows)
    issues = []
    seen = set()
    if not failed:
        for row in rows:
            for issue in row.get("issues") or []:
                key = (issue["repo"], int(issue["issue"]))
                if key not in seen:
                    seen.add(key)
                    issues.append(dict(issue))
    return {
        "ok": True,
        "route": "failed" if failed else "probed",
        "repo": selected["repo"],
        "issues": issues,
    }

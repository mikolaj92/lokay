"""Select whether one repository needs a physical PR relist."""

from lokay.passkit.working import load_begin_working


def inspect(*, pass_dir: str, selected: dict, facts: dict) -> dict:
    _, working = load_begin_working(pass_dir)
    repo = str(selected["repo"])
    previous = list((working.get("prs_by_repo") or {}).get(repo) or [])
    ready = list((working.get("ready_by_repo") or {}).get(repo) or [])
    reason = (
        "occupied"
        if repo in set(facts.get("occupied") or [])
        else "no_ready" if not ready else "list"
    )
    return {
        "ok": True,
        "route": reason,
        "repo": repo,
        "slot": selected["slot"],
        "previous": previous,
    }

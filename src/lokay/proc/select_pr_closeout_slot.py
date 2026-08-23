"""Select exactly one AI PR for one authored repository slot."""


def select(prepared: dict, previous: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    budget = int(previous.get("repair_budget", prepared.get("repair_budget") or 0))
    if slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot, "repair_budget": budget}
    repo = str(repos[slot - 1])
    prs = list((prepared.get("prs_by_repo") or {}).get(repo) or [])
    if len(prs) > 1:
        return {
            "ok": True,
            "route": "needs_human",
            "reason": "multiple_open_ai_prs",
            "slot": slot,
            "repo": repo,
            "prs": [int(x.get("number") or 0) for x in prs],
            "repair_budget": budget,
        }
    return {
        "ok": True,
        "route": "closeout" if prs else "empty",
        "slot": slot,
        "repo": repo,
        "pr": prs[0] if prs else {},
        "repair_budget": budget,
        "policy": dict(prepared.get("policy") or {}),
    }

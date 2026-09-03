"""Select exactly one AI PR for one authored repository slot."""

from lokay.proc.pass_lane import is_oil_repo, product_candidates, self_repo


def select(prepared: dict, previous: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    budget = int(previous.get("repair_budget", prepared.get("repair_budget") or 0))
    if previous.get("route") == "failed":
        return {
            "ok": True,
            "route": "empty",
            "reason": "upstream_failed",
            "slot": slot,
            "repair_budget": budget,
        }
    if slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot, "repair_budget": budget}
    repo = str(repos[slot - 1])
    self_id = str(prepared.get("self_repo") or self_repo())
    product_queue = bool(prepared.get("product_queue")) or product_candidates(
        ready_by_repo=prepared.get("ready_by_repo"),
        prs_by_repo=prepared.get("prs_by_repo"),
        self_id=self_id,
    )
    if product_queue and is_oil_repo(repo, self_id=self_id):
        return {
            "ok": True,
            "route": "empty",
            "reason": "product_lane",
            "slot": slot,
            "repo": repo,
            "repair_budget": budget,
        }
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

"""Run the authored PR-repair sub-Fala once."""

from lokay.compose.pr_repair import compose_pr_repair


def repair(gate: dict, authorized: dict, *, config_path: str | None) -> dict:
    item = gate["inspected"]
    kw = {
        "config_path": config_path,
        "repo": item["repo"],
        "pr_number": item["pr_number"],
        "branch": item["head"],
        "live": True,
    }
    review = authorized.get("review") or None
    if review is not None:
        kw["review"] = review
    out = compose_pr_repair(**kw)
    return {
        "ok": True,
        "repair": out,
        "repair_used": 1,
        "step": authorized.get("step") or "pr_repair",
    }

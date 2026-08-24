"""Build the closed one-retry off-goal agent request."""

from lokay.localize_agent import localize_prompt


def build(evidence: dict, offgoal: dict) -> dict:
    off = offgoal.get("off_goal_paths") or []
    localized = evidence.get("localized") or []
    seed = f"One bounded relocalization retry. Changed outside scope: {off}. Original scope: {localized}. Return only off-goal paths genuinely required for the same issue."
    return {
        "ok": True,
        "route": "agent" if offgoal.get("route") == "agent" else "unused",
        "prompt": localize_prompt(
            seed_text=seed, tree_sample=off, extra_paths=[], max_paths=40
        ),
    }

"""Read whether one over-budget wrapper still has a coder descendant."""

from lokay.proc.detach_issue_to_pr import (
    coding_live_for_issue,
    wrapper_has_coding_descendant,
)


def inspect(budget: dict) -> dict:
    live = wrapper_has_coding_descendant(int(budget["pid"]))
    if not live:
        try:
            issue = int(budget.get("issue") or 0)
        except (TypeError, ValueError):
            issue = 0
        live = bool(issue > 0 and coding_live_for_issue(issue))
        if live:
            # Orphan after a dead wrapper is occupancy, not a second harvest.
            return {**budget, "route": "reap", "coder_live": True}
    return {**budget, "route": "diff" if live else "reap", "coder_live": live}

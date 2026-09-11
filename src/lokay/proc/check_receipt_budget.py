"""Read elapsed time and budget status for one detached worker."""

from lokay.proc.issue_delivery_process import coding_live_for_issue, pid_is_alive
from lokay.proc.pi_budget import check_pi_budget


def check(selected: dict, issue_state: dict, *, budget_s: int) -> dict:
    result = check_pi_budget(int(selected["pid"]), budget_s)
    over_budget = bool(result.get("over_budget"))
    if not over_budget:
        try:
            issue = int(selected.get("issue") or 0)
        except (TypeError, ValueError):
            issue = 0
        # Dead wrapper reports elapsed=0. An orphan coder is still the slot.
        wrapper_dead = not pid_is_alive(int(selected["pid"]))
        if issue > 0 and wrapper_dead and coding_live_for_issue(issue):
            over_budget = True
    covering = bool(issue_state.get("covering"))
    done = bool(issue_state.get("closed") or covering)
    return {
        **selected,
        "closed": bool(issue_state.get("closed")),
        "covering": covering,
        "elapsed_s": float(result.get("elapsed_s") or 0),
        "over_budget": over_budget,
        "route": (
            "reap"
            if done
            else "inspect_coder" if over_budget else "keep"
        ),
    }

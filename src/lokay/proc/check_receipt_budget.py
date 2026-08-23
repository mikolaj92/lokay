"""Read elapsed time and budget status for one detached worker."""

from lokay.proc.pi_budget import check_pi_budget


def check(selected: dict, issue_state: dict, *, budget_s: int) -> dict:
    result = check_pi_budget(int(selected["pid"]), budget_s)
    return {
        **selected,
        "closed": bool(issue_state.get("closed")),
        "elapsed_s": float(result.get("elapsed_s") or 0),
        "over_budget": bool(result.get("over_budget")),
        "route": (
            "reap"
            if issue_state.get("closed")
            else "inspect_coder" if result.get("over_budget") else "keep"
        ),
    }

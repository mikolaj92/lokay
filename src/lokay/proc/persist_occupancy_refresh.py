"""Persist one already-reduced occupancy refresh state."""

from lokay.passkit.working import load_begin_working, save_begin_working


def persist(*, pass_dir: str, reduced: dict) -> dict:
    begin, _ = load_begin_working(pass_dir)
    state = dict(reduced["state"])
    save_begin_working(pass_dir, begin, state)
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "occupied_repos": state["occupied_repos"],
        "merged_this_pass": state["merged_this_pass"],
        "live_issue_to_pr_repos": state["live_issue_to_pr_repos"],
        "cleared_issue_to_pr_receipts": state["cleared_issue_to_pr_receipts"],
        "remaining_prs": int(state.get("remaining_prs") or 0),
        "actionable_prs": int(state.get("actionable_prs") or 0),
        "survey_errors": int(state.get("survey_errors") or 0),
        "probe_failed": bool(state.get("pr_survey_failed")),
        "receipt_state_unknown": bool(state.get("receipt_state_unknown")),
    }

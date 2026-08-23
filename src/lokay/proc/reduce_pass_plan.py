"""Purely reduce repository fragments under one global triage budget."""


def reduce_state(*, prepared: dict, fragments: list[dict], working: dict) -> dict:
    budget = int(prepared.get("triage_budget") or 0)
    triage = []
    closeout = []
    implement = []
    actions = list(working.get("actions") or [])
    for repo in prepared.get("skipped_repos") or []:
        actions.append(
            {
                "step": "skip_repo_outside_mini_mill",
                "repo": repo,
                "ok": True,
                "skipped": True,
                "reason": "outside configured mill scope",
            }
        )
    for row in fragments:
        actions.extend(list(row.get("actions") or []))
        closeout.extend(list(row.get("closeout") or []))
        implement.extend(list(row.get("implement") or []))
        available = list(row.get("triage") or [])
        take = min(budget, len(available))
        triage.extend(available[:take])
        budget -= take
    return {
        "ok": True,
        "plan": {
            "triage_targets": triage,
            "closeout_targets": closeout,
            "implement_candidates": implement,
            "triage_budget_remaining": budget,
        },
        "actions": actions,
    }

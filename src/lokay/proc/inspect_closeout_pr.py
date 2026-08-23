"""Purely inspect one selected PR's physical metadata."""

from lokay.passkit.support import is_manual_pr
from lokay.stuck import issue_number_from_branch


def inspect(selected: dict) -> dict:
    pr = dict(selected.get("pr") or {})
    head = str(pr.get("head_ref") or "")
    policy = dict(selected.get("policy") or {})
    issue = issue_number_from_branch(
        head, branch_prefix=str(policy.get("branch_prefix") or "ai/fix/")
    )
    mergeable = str(pr.get("mergeable") or "").upper()
    route = (
        "manual"
        if is_manual_pr(pr)
        else "conflict" if mergeable in {"CONFLICTING", "DIRTY"} else "checks"
    )
    return {
        **selected,
        "route": route,
        "pr_number": int(pr.get("number") or 0),
        "head": head,
        "issue": issue,
    }

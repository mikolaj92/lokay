"""Classify the deepest coder worktree and branch as a physical fact."""

from lokay.proc.over_budget_coder_facts import coder_diff, worktree_branch


def inspect(coder: dict) -> dict:
    fact = coder_diff(int(coder["pid"]))
    kind = str(fact.get("kind") or "unknown")
    worktree = str(fact.get("worktree") or "")
    branch = worktree_branch(worktree)
    return {
        **coder,
        "route": (
            "harvest"
            if kind == "real" and worktree and branch
            else "reap" if kind != "unknown" else "keep"
        ),
        "diff_kind": kind,
        "worktree": worktree,
        "branch": branch,
    }

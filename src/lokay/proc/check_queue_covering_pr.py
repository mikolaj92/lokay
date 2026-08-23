"""Check the hard fact that an open PR already covers one candidate."""

from lokay.passkit.io import begin_path, read_json, working_path
from lokay.queue_conflict_agent import covering_pr_numbers
from lokay.models import Issue


def check(*, pass_dir: str, target: dict) -> dict:
    repo = str(target["repo"])
    candidate = dict(target["candidate"])
    working = read_json(working_path(pass_dir))
    prs = list((working.get("prs_by_repo") or {}).get(repo) or [])
    issue = Issue.from_dict({**candidate, "repo": repo})
    numbers = covering_pr_numbers(
        issue,
        prs,
        branch_prefix=str(
            read_json(begin_path(pass_dir)).get("branch_prefix") or "ai/fix/"
        ),
    )
    if numbers:
        return {
            "ok": True,
            "route": "covered",
            "decision": {
                "outcome": "close",
                "reason": "open_ai_pr_covers_issue",
                "detail": {"issue": issue.number, "prs": numbers},
                "summary": f"Open AI PR already covers #{issue.number}.",
                "add_tracker": False,
            },
            **target,
        }
    peers = list((working.get("ready_by_repo") or {}).get(repo) or []) + list(
        (working.get("inbox_issues_by_repo") or {}).get(repo) or []
    )
    return {
        "ok": True,
        "route": "agent",
        "open_prs": prs,
        "peer_issues": peers,
        **target,
    }

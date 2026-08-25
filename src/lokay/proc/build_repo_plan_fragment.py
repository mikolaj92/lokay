"""Build one repository-local deterministic plan fragment."""

from lokay.passkit import io as pass_io
from lokay.passkit.support import is_manual_pr
from lokay.proc.catalog_work import work_by_repo
from lokay.stuck import is_blocked_in_ledger


def build(*, pass_dir: str, prepared: dict, selected: dict) -> dict:
    repo = str(selected["repo"])
    survey = pass_io.read_json(pass_io.survey_path(pass_dir))
    prs = list((survey.get("prs_by_repo") or {}).get(repo) or [])
    inbox = list((survey.get("inbox_issues_by_repo") or {}).get(repo) or [])
    ready = list(
        work_by_repo(survey, stuck=prepared.get("stuck")).get(repo) or []
    )
    actions = []
    triage = []
    if prepared.get("live") and inbox:
        if repo in set(survey.get("pr_survey_failed") or []):
            actions.append(
                {
                    "step": "skip_inbox_triage_survey_failed",
                    "repo": repo,
                    "count": len(inbox),
                    "reason": "PR survey failed closed for this repo; refuse inbox triage",
                }
            )
        elif any(not is_manual_pr(pr) for pr in prs):
            actions.append(
                {
                    "step": "skip_inbox_triage_repo_backpressure",
                    "repo": repo,
                    "count": len(inbox),
                    "actionable_open_ai_prs": sum(not is_manual_pr(pr) for pr in prs),
                    "reason": "per-repo PR-first",
                }
            )
        else:
            for issue in inbox:
                number = int(issue["number"])
                if is_blocked_in_ledger(
                    dict(prepared.get("stuck") or {}), repo, number
                ):
                    actions.append(
                        {
                            "step": "skip_inbox_triage_stuck_blocked",
                            "repo": repo,
                            "issue": number,
                            "ok": True,
                            "skipped": True,
                            "blocked": True,
                            "reason": "blocked_in_stuck_ledger",
                        }
                    )
                else:
                    triage.append({"repo": repo, "issue": number})
    closeout = [
        {
            "repo": repo,
            "pr": int(pr["number"]),
            "head_ref": str(pr.get("head_ref") or ""),
            "mergeable": str(pr.get("mergeable") or ""),
            "manual": is_manual_pr(pr),
            "labels": (
                list(pr.get("labels") or [])
                if isinstance(pr.get("labels"), list)
                else pr.get("labels")
            ),
            "title": str(pr.get("title") or ""),
        }
        for pr in prs
    ]
    implement = [
        {
            "repo": repo,
            "number": int(issue.get("number")),
            "title": str(issue.get("title") or ""),
        }
        for issue in ready
    ]
    return {
        "ok": True,
        "route": "fragment",
        "repo": repo,
        "slot": selected["slot"],
        "triage": triage,
        "closeout": closeout,
        "implement": implement,
        "actions": actions,
    }

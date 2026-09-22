"""Fresh repository PR-first fact, shared by admission and locked launch."""

from __future__ import annotations

import re

from lokay.config import Config
from lokay.gh_prs import list_open_ai_prs
from lokay.passkit.support import is_manual_pr
from lokay.runner import Runner


def inspect(*, runner: Runner, config: Config, repo: str, issue: int, live: bool) -> dict:
    if not live:
        return {"allowed": False, "reason": "pr_survey_unavailable", "planned": True}
    try:
        row = next(row for row in config.repos if row.name == repo and row.enabled)
        prs = list_open_ai_prs(runner, config, row, live=True)
    except Exception:  # noqa: BLE001 - any survey/adapter failure denies admission
        return {"allowed": False, "reason": "pr_survey_unavailable"}
    closes_issue = re.compile(
        rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#{issue}\b", re.IGNORECASE
    )
    blockers = [
        pr.to_dict() for pr in prs
        if not is_manual_pr(pr.to_dict()) and not closes_issue.search(pr.body)
    ]
    if blockers:
        return {"allowed": False, "reason": "actionable_pr", "blocking_prs": blockers}
    return {"allowed": True, "reason": "pr_first_clear"}

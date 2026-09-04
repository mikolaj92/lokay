"""Residual human mailbox survey (exception reporting, not a lokay brake).

Lists issues labeled needs-feedback and PRs labeled needs-review for the Lokay
mini lokay repository. Presence of these items does **not** mean the lokay is stuck —
humans are a mailbox for rare residuals while other work continues.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import ok
from lokay.gh_issues import list_issues_with_label
from lokay.gh_prs import list_open_ai_prs
from lokay.proc._common import load_cfg, runner




def compose_human_mailbox(*, config_path: str | None, live: bool = True) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    r = runner(cfg)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    repos = list(cfg.active_repos())

    for repo in repos:
        try:
            feedback = list_issues_with_label(
                r,
                cfg,
                repo,
                label=cfg.needs_feedback_label,
                live=live,
            )
            for issue in feedback:
                items.append(
                    {
                        "kind": "issue",
                        "repo": repo.name,
                        "number": issue.number,
                        "title": issue.title,
                        "url": issue.url,
                        "label": cfg.needs_feedback_label,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append({"repo": repo.name, "step": "list_needs_feedback", "error": str(exc)})

        try:
            prs = list_open_ai_prs(r, cfg, repo, live=live)
            for pr in prs:
                labels = pr.labels or []
                if "ai:needs-review" not in labels:
                    continue
                items.append(
                    {
                        "kind": "pr",
                        "repo": repo.name,
                        "number": pr.number,
                        "title": pr.title,
                        "url": pr.url,
                        "label": "ai:needs-review",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append({"repo": repo.name, "step": "list_needs_review_prs", "error": str(exc)})

    return ok(
        kind="human_mailbox",
        config=str(cfg.config_path),
        lokay_blocked=False,
        note=(
            "Human queue is exception reporting only — lokay continues other repos. "
            "NEEDS_HUMAN / ai:needs-feedback must stay rare."
        ),
        count=len(items),
        items=items,
        errors=errors,
        repos=[repo.name for repo in repos],
    )

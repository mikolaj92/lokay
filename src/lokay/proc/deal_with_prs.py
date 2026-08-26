"""Parent step (2): deal with PRs on the repo in hand — merge, fix, triage."""

from __future__ import annotations


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    from lokay.proc.closeout_prs_subflow import run as closeout
    from lokay.proc.resolve_conflicts_subflow import run as conflicts
    from lokay.proc.survey_prs_subflow import run as survey_prs

    surveyed = survey_prs(pass_dir=pass_dir, config_path=config_path, live=live)
    resolved = conflicts(pass_dir=pass_dir, config_path=config_path, live=live)
    closed = closeout(pass_dir=pass_dir, config_path=config_path, live=live)
    return {
        "ok": True,
        "route": "prs",
        "pass_dir": pass_dir,
        "survey_prs": surveyed,
        "resolve_conflicts": resolved,
        "closeout_prs": closed,
    }

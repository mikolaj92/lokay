"""Purely build one immutable factory-begin payload."""


def build(
    config: dict, scope: dict, ledger: dict, workspace: dict, survey: dict
) -> dict:
    repos = list(scope.get("repos") or [])
    pipeline = [
        "survey: list-prs + list-inbox + list-issues (hot repos + rotated cold)",
        "per-repo PR-first: conflict close / repair / merge open AI PRs",
        "inbox triage + deterministic intake (skip repos with actionable open AI PRs)",
        "issue_to_pr up to K across clean (not occupied) repos; occupancy and leftover reaps are housecleaning",
        "on failure: stuck ledger → ai:blocked",
    ]
    planned = [
        {
            "kind": "tick",
            "status": "mutating" if config.get("live") else "survey",
            "repos": repos,
            "agent": config.get("agent"),
            "pipeline": pipeline,
        }
    ]
    return {
        "ok": True,
        "begin": {
            **config,
            "pass_dir": workspace["pass_dir"],
            "repos": repos,
            "survey_repos": survey["survey_repos"],
            "stuck_path": ledger["stuck_path"],
            "planned": planned,
        },
    }

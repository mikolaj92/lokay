"""Purely build one immutable factory-begin payload."""


def build(
    config: dict, scope: dict, ledger: dict, workspace: dict, survey: dict | None = None
) -> dict:
    repos = list(scope.get("repos") or [])
    catalog = list((survey or {}).get("survey_repos") or repos)
    pipeline = [
        "open workspace + configured catalog",
        "prs and issues list live from GitHub",
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
            "survey_repos": catalog,
            "stuck_path": ledger["stuck_path"],
            "planned": planned,
        },
    }

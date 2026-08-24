"""Purely select hot and rotated cold repositories for one pass."""

from lokay.passkit.hot import load_last_pass_by_repo, pick_survey_repos


def select(config: dict, scope: dict, workspace: dict) -> dict:
    repos = list(scope.get("repos") or [])
    rows = pick_survey_repos(
        repos,
        load_last_pass_by_repo(config["state_path"]),
        salt=workspace["pass_dir"],
        extra_cold=max(2, int(config["max_issue_to_pr_per_pass"])),
    )
    return {"ok": True, "survey_repos": rows}

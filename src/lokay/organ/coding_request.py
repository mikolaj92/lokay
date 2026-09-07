"""Bind one coding request from authored inputs and upstream evidence."""
from lokay.organ.common import _worktree_path, _issue_raw

def prepare_request(inputs, up, ctx):
    from lokay.proc.prepare_coding_request import prepare

    return prepare(
        worktree=_worktree_path(up, inputs),
        repo=str(ctx.get("repo") or inputs.get("repo") or ""),
        issue=ctx.get("issue_number")
        if ctx.get("issue_number") is not None
        else inputs.get("issue"),
        issue_raw=_issue_raw(up, inputs),
        localize=dict(inputs.get("localize") or up.get("localize") or {}),
        branch=str(
            (up.get("make_branch") or {}).get("branch")
            or inputs.get("branch")
            or ""
        ),
        live=bool(inputs.get("live")),
        repo_map=str(
            (inputs.get("map_repo") or {}).get("map")
            or (up.get("map_repo") or {}).get("map")
            or ""
        ),
    )

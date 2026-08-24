"""Fala bindings for authored deterministic issue planning."""

from typing import Any


def handle_plan_issue(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    request = up.get("prepare_issue_plan_request") or {}
    approach = up.get("build_issue_approach") or {}
    authorized = up.get("authorize_issue_plan_write") or {}
    if atom == "prepare_issue_plan_request":
        from lokay.proc.prepare_issue_plan_request import prepare

        return prepare(
            worktree=str(inputs.get("worktree") or ""),
            issue_raw=dict(inputs.get("issue_raw") or {}),
            repo=str(inputs.get("repo") or ""),
            issue=int(inputs["issue"]) if inputs.get("issue") is not None else None,
            title=str(inputs.get("title") or ""),
            body=str(inputs.get("body") or ""),
            url=str(inputs.get("url") or ""),
            rel_path=str(inputs.get("rel_path") or ".lokay/approach.md"),
        )
    if atom == "build_issue_approach":
        from lokay.proc.build_issue_approach import build

        return build(request)
    if atom == "authorize_issue_plan_write":
        from lokay.proc.authorize_issue_plan_write import authorize

        return authorize(
            request,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )
    if atom == "write_issue_approach":
        from lokay.proc.write_issue_approach import write

        return write(request, approach)
    if atom == "record_issue_approach_write":
        from lokay.proc.record_issue_approach_write import record

        return record(authorized, up.get("write_issue_approach") or {})
    if atom == "issue_plan_terminal":
        from lokay.proc.issue_plan_terminal import terminal

        return terminal(
            request, approach, authorized, up.get("record_issue_approach_write") or {}
        )
    return None

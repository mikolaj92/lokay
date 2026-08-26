"""Fala bindings for the issues child: list, sito, kod i PR."""

from typing import Any


def handle_issues(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "list_open_issues":
        from lokay.proc.list_open_issues import run

        return run(config_path=config, live=live)
    if atom == "select_next_issue":
        from lokay.proc.select_next_issue import select

        return select(up.get("list_open_issues") or {})
    if atom == "issues_run_triage":
        from lokay.proc.run_issue_triage_subflow import run

        picked = up.get("select_next_issue") or {}
        if picked.get("route") != "issue":
            return {"ok": True, "route": "skip", "reason": "no_issue"}
        return run(picked, config_path=config)
    if atom == "select_issue_do":
        from lokay.proc.select_issue_do import select

        return select(
            up.get("select_next_issue") or {},
            up.get("issues_run_triage") or {},
        )
    if atom == "issues_launch_pr":
        from lokay.proc.launch_issue_to_pr import launch

        chosen = up.get("select_issue_do") or {}
        if chosen.get("route") != "do":
            return {"ok": True, "route": "skip", "reason": "sito_nie_robic"}
        return launch(chosen, config_path=config)
    if atom == "summarize_issues":
        from lokay.proc.summarize_issues import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_do") or {},
            up.get("issues_launch_pr") or {},
            pass_dir=str(inputs.get("pass_dir") or ""),
        )
    return None

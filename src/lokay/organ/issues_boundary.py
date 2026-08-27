"""Fala bindings for the issues NODE: six wired atoms, no fat step."""

import os
from typing import Any


def _last_queue() -> dict[str, Any]:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    from lokay.pass_receipt import read_pass_receipt

    receipt = read_pass_receipt() or {}
    rem = receipt.get("remaining")
    return rem if isinstance(rem, dict) else {}


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

        return select(up.get("list_open_issues") or {}, _last_queue())
    if atom == "issues_run_triage":
        from lokay.proc.run_issue_triage_subflow import run

        return run(up.get("select_next_issue") or {}, config_path=config)
    if atom == "select_issue_do":
        from lokay.proc.select_issue_do import select

        return select(
            up.get("select_next_issue") or {},
            up.get("issues_run_triage") or {},
            up.get("list_open_issues") or {},
        )
    if atom == "issues_launch_pr":
        from lokay.proc.launch_issue_to_pr import launch

        return launch(up.get("select_issue_do") or {}, config_path=config)
    if atom == "summarize_issues":
        from lokay.proc.summarize_issues import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_do") or {},
            up.get("issues_launch_pr") or {},
            pass_dir=str(inputs.get("pass_dir") or ""),
        )
    return None

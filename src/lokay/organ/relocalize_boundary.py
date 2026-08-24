"""Fala bindings for authored one-retry off-goal relocalization."""

import argparse
from typing import Any


def handle_relocalize(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config_path = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    evidence = up.get("inspect_relocalization_evidence") or {}
    changed = up.get("read_relocalization_changed_paths") or {}
    offgoal = up.get("classify_relocalization_off_goal") or {}
    request = up.get("build_relocalization_agent_request") or {}
    if atom == "inspect_relocalization_evidence":
        from lokay.proc.inspect_relocalization_evidence import inspect

        return inspect(worktree=str(inputs.get("worktree") or ""))
    if atom == "read_relocalization_changed_paths":
        from lokay.proc.read_relocalization_changed_paths import read

        return read(evidence, base=str(inputs.get("base") or "origin/main"))
    if atom == "read_relocalization_issue_paths":
        from lokay.proc.read_relocalization_issue_paths import read

        return read(dict(inputs.get("issue_raw") or {}))
    if atom == "classify_relocalization_residue":
        from lokay.proc.classify_relocalization_residue import classify

        return classify(changed, up.get("read_relocalization_issue_paths") or {})
    if atom == "authorize_relocalization_restore":
        from lokay.proc.authorize_relocalization_restore import authorize

        return authorize(
            up.get("classify_relocalization_residue") or {},
            config_path=config_path,
            live=live,
        )
    if atom == "restore_relocalization_residue":
        from lokay.proc.restore_relocalization_residue import restore

        return restore(
            evidence, changed, up.get("authorize_relocalization_restore") or {}
        )
    if atom == "record_relocalization_restore":
        from lokay.proc.record_relocalization_restore import record

        return record(
            up.get("classify_relocalization_residue") or {},
            up.get("authorize_relocalization_restore") or {},
            up.get("restore_relocalization_residue") or {},
        )
    if atom == "classify_relocalization_off_goal":
        from lokay.proc.classify_relocalization_off_goal import classify

        return classify(
            evidence, changed, up.get("record_relocalization_restore") or {}
        )
    if atom == "build_relocalization_agent_request":
        from lokay.proc.build_relocalization_agent_request import build

        return build(evidence, offgoal)
    if atom in {"run_relocalization_agent", "retry_relocalization_agent"}:
        from lokay.proc._common import load_cfg
        from lokay.proc.run_relocalization_agent import run

        cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
        feedback = (
            str((up.get("build_relocalization_retry") or {}).get("feedback") or "")
            if atom.startswith("retry")
            else ""
        )
        return run(evidence, request, config=cfg, feedback=feedback)
    if atom in {
        "validate_relocalization_agent_json",
        "validate_relocalization_retry_json",
    }:
        from lokay.proc.validate_localization_agent_json import validate

        source = (
            up.get("retry_relocalization_agent")
            if atom.endswith("retry_json")
            else up.get("run_relocalization_agent")
        )
        return validate(source or {})
    if atom == "build_relocalization_retry":
        from lokay.proc.build_localization_retry import build

        return build(up.get("validate_relocalization_agent_json") or {})
    if atom == "select_relocalization_validation":
        first = up.get("validate_relocalization_agent_json") or {}
        retry = up.get("validate_relocalization_retry_json") or {}
        transport = up.get("run_relocalization_agent") or {}
        again = up.get("retry_relocalization_agent") or {}
        if first.get("route") == "valid":
            return first
        if retry.get("route") == "valid":
            return retry
        reason = (
            "invalid_json"
            if retry.get("route") == "invalid"
            else str(
                again.get("reason")
                or transport.get("reason")
                or "off_goal_not_approved"
            )
        )
        return {"ok": True, "route": "terminal", "reason": reason}
    if atom == "validate_relocalization_approval":
        from lokay.proc.validate_relocalization_approval import validate

        return validate(up.get("select_relocalization_validation") or {}, offgoal)
    if atom == "write_relocalization_evidence":
        from lokay.proc.write_relocalization_evidence import write

        return write(
            evidence,
            offgoal,
            up.get("validate_relocalization_approval") or {},
            config_path=config_path,
            live=live,
        )
    if atom == "relocalization_terminal":
        from lokay.proc.relocalization_terminal import terminal

        return terminal(
            evidence,
            changed,
            offgoal,
            up.get("validate_relocalization_approval") or {},
            up.get("write_relocalization_evidence") or {},
        )
    return None

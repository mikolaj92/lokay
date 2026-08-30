"""Fala bindings for factory_pass department switches and department bodies."""

from typing import Any


def _pass_dir(up: dict[str, dict[str, Any]]) -> str:
    return str(up.get("factory_begin", {}).get("pass_dir") or "")


def _department_enabled(config: str | None, name: str) -> bool:
    from lokay.config import department_enabled, load_config

    if not config:
        return True
    try:
        return department_enabled(load_config(config), name)
    except FileNotFoundError:
        return True


def _host_restart(up: dict[str, dict[str, Any]]) -> bool:
    gate = up.get("factory_begin_host_gate") or {}
    return str(gate.get("route") or "") == "restart"


def _skip_host_updated() -> dict[str, Any]:
    from lokay.envelope import ok

    return ok(route="skip", reason="host_updated", health="host_updated")


def handle_departments(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "select_self_repair_department":
        if _host_restart(up):
            return _skip_host_updated()
        from lokay.pass_receipt import read_pass_receipt
        from lokay.proc.last_pass_moving import classify as classify_moving
        from lokay.proc.leftover_skip import classify as classify_leftover
        from lokay.proc.select_self_repair_department import select

        receipt = read_pass_receipt()
        moving = classify_moving(receipt)
        leftover = classify_leftover(receipt)
        return select(
            enabled=_department_enabled(config, "self_repair"),
            moved_forward=bool(moving.get("moved_forward")),
            receipt_present=isinstance(receipt, dict) and bool(receipt),
            leftover_skip=bool(leftover.get("leftover_skip")),
            receipt=receipt if isinstance(receipt, dict) else None,
        )
    if atom == "run_self_repair_department":
        from lokay.proc.run_self_repair_department import run

        return run(config_path=config)
    if atom == "open_self_repair_incident":
        from lokay.proc.open_self_repair_incident import run

        return run(config_path=config)
    if atom == "invoke_self_repair":
        from lokay.proc.invoke_self_repair import run

        return run(up.get("open_self_repair_incident") or {}, config_path=config)
    if atom == "select_issue_triage_department":
        if _host_restart(up):
            return _skip_host_updated()
        from lokay.proc.select_issue_triage_department import select

        return select(enabled=_department_enabled(config, "issue_triage"))
    if atom == "run_issue_triage_department":
        from lokay.proc.run_issue_triage_department import run

        return run(pass_dir=_pass_dir(up), config_path=config, live=live)
    if atom == "select_executor_department":
        if _host_restart(up):
            return _skip_host_updated()
        from lokay.proc.select_executor_department import select

        return select(enabled=_department_enabled(config, "executor"))
    if atom == "run_executor_department":
        from lokay.proc.run_executor_department import run

        select = up.get("select_issue_triage_department") or {}
        return run(
            pass_dir=_pass_dir(up),
            config_path=config,
            live=live,
            triage_ran=str(select.get("route") or "") == "run",
        )
    if atom == "select_pr_triage_department":
        if _host_restart(up):
            return _skip_host_updated()
        from lokay.proc.select_pr_triage_department import select

        return select(enabled=_department_enabled(config, "pr_triage"))
    if atom == "run_pr_triage_department":
        from lokay.proc.run_pr_triage_department import run

        return run(pass_dir=_pass_dir(up), config_path=config, live=live)
    if atom == "select_pr_repair_department":
        if _host_restart(up):
            return _skip_host_updated()
        from lokay.proc.select_pr_repair_department import select

        select_pr = up.get("select_pr_triage_department") or {}
        triage = up.get("run_pr_triage_department") or {}
        return select(
            triage,
            enabled=_department_enabled(config, "pr_repair"),
            triage_ran=str(select_pr.get("route") or "") == "run",
        )
    if atom == "run_pr_repair_department":
        from lokay.proc.run_pr_repair_department import run

        return run(
            up.get("select_pr_repair_department") or {},
            config_path=config,
            live=live,
        )
    return None

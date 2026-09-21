"""Fala bindings for the pr_triage department (PR sieve, not repair)."""

from typing import Any


def _last_of(inputs: dict[str, Any]) -> dict[str, Any]:
    last = inputs.get("last") or {}
    return last if isinstance(last, dict) else {}


def handle_pr_triage_department(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "list_pr_sieve":
        from lokay.proc.list_open_prs import run

        return run(config_path=config, live=live)
    if atom == "select_pr_sieve":
        from lokay.proc.select_next_pr import select

        return select(up.get("list_pr_sieve") or {}, last=_last_of(inputs))
    if atom == "reconcile_pr_repair_push":
        from lokay.proc.reconcile_pr_repair_push import reconcile_pending

        picked = dict(up.get("select_pr_sieve") or {})
        return {"recovery_case": "none", **reconcile_pending(config_path=config, live=live, selection=picked)}
    if atom.startswith("recover_repair_"):
        from lokay.proc import pr_repair_receipts as receipts
        from lokay.proc.pr_repair_recovery import retry

        observed = dict(up.get("reconcile_pr_repair_push") or {})
        if atom in {"recover_repair_pre_attempt", "recover_repair_remote_unchanged"}:
            state = receipts.resolve_state_dir(config)
            if live and state is not None:
                result = retry(repo=str(observed["repo"]), pr=int(observed["pr"]),
                               config_path=config, state_dir=state)
                return {**observed, **result, "route": "fail_closed"}
        if atom == "recover_repair_closed_merged" and live:
            from lokay.proc.pr_repair_recovery import close_pending
            return close_pending(observed=observed, config_path=config)
        return observed
    if atom == "run_pr_sieve":
        from lokay.proc.run_pr_triage_subflow import run

        selected = dict(up.get("select_pr_sieve") or {})
        if selected.get("route") != "pr":
            reconciled = dict(up.get("reconcile_pr_repair_push") or {})
            if reconciled.get("route") == "review":
                selected = {
                    "ok": True,
                    "route": "pr",
                    "repo": reconciled.get("repo"),
                    "pr": reconciled.get("pr"),
                    "branch": reconciled.get("branch"),
                }
        return run(selected, config_path=config, live=live)
    recovery = next((dict(up[name]) for name in (
        "recover_repair_pre_attempt", "recover_repair_remote_unchanged",
        "recover_repair_confirmed_target", "recover_repair_closed_merged", "recover_repair_unavailable",
    ) if up.get(name) and up[name].get("route")), dict(up.get("reconcile_pr_repair_push") or {}))
    if atom == "select_pr_triage_verdict":
        from lokay.proc.select_pr_triage_verdict import select

        return select(
            up.get("select_pr_sieve") or {},
            up.get("run_pr_sieve") or {},
            recovery,
        )
    if atom == "summarize_pr_triage_department":
        from lokay.proc.summarize_pr_triage_department import summarize

        return summarize(
            up.get("select_pr_sieve") or {},
            up.get("run_pr_sieve") or {},
            up.get("select_pr_triage_verdict") or {},
            recovery,
            incomplete_retry_position=str(inputs.get("incomplete_retry_position") or "head"),
        )
    return None

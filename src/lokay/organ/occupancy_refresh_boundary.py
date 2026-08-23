"""Fala bindings for explicit receipt and repository occupancy slots."""

from typing import Any

SLOT_COUNT = 30


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def handle_occupancy_refresh(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_occupancy_refresh":
        from lokay.proc.prepare_occupancy_refresh import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    if atom == "clear_merged_dead_receipts":
        from lokay.proc.clear_merged_dead_receipts import clear

        return clear(up.get("prepare_occupancy_refresh") or {})
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_live_receipt_"):
        from lokay.proc.select_live_receipt_slot import select

        return select(up.get("prepare_occupancy_refresh") or {}, slot=slot)
    if atom.startswith("inspect_live_receipt_issue_"):
        from lokay.proc.inspect_live_receipt_issue import inspect

        return inspect(
            up.get(f"select_live_receipt_{slot}") or {}, config_path=config, live=live
        )
    if atom.startswith("select_live_receipt_issue_gate_"):
        selected = up.get(f"select_live_receipt_{slot}") or {}
        inspected = up.get(f"select_live_receipt_issue_gate_{slot}") or {}
        return (
            inspected
            if selected.get("route") == "receipt"
            else {"ok": True, "route": "empty", "slot": slot}
        )
    if atom.startswith("terminate_closed_issue_worker_"):
        from lokay.proc.terminate_closed_issue_worker import terminate

        return terminate(up.get(f"select_live_receipt_issue_gate_{slot}") or {})
    if atom.startswith("select_live_receipt_issue_outcome_"):
        inspected = up.get(f"inspect_live_receipt_issue_{slot}") or {}
        terminated = up.get(f"terminate_closed_issue_worker_{slot}") or {}
        if inspected.get("route") != "closed":
            return inspected
        return {
            **inspected,
            "route": "terminated" if terminated.get("terminated") else "keep",
            "terminated": bool(terminated.get("terminated")),
        }
    if atom.startswith("clear_closed_issue_receipt_"):
        from lokay.proc.clear_closed_issue_receipt import clear

        return clear(up.get(f"select_live_receipt_issue_outcome_{slot}") or {})
    if atom.startswith("record_live_receipt_outcome_"):
        from lokay.proc.record_live_receipt_outcome import record

        return record(
            up.get(f"select_live_receipt_{slot}") or {},
            up.get(f"select_live_receipt_issue_outcome_{slot}") or {},
            up.get(f"select_live_receipt_issue_outcome_{slot}") or {},
            up.get(f"clear_closed_issue_receipt_{slot}") or {},
        )
    if atom == "reduce_occupancy_facts":
        from lokay.proc.reduce_occupancy_facts import reduce_state

        results = [
            up.get(f"record_live_receipt_outcome_{i}") or {}
            for i in range(1, SLOT_COUNT + 1)
        ]
        return reduce_state(
            prepared=up.get("prepare_occupancy_refresh") or {},
            merged_clear=up.get("clear_merged_dead_receipts") or {},
            results=results,
        )
    if atom.startswith("select_occupancy_repo_"):
        from lokay.proc.select_occupancy_repo_slot import select

        return select(up.get("prepare_occupancy_refresh") or {}, slot=slot)
    if atom.startswith("inspect_repo_pr_refresh_"):
        from lokay.proc.inspect_repo_pr_refresh import inspect

        return inspect(
            pass_dir=pass_dir,
            selected=up.get(f"select_occupancy_repo_{slot}") or {},
            facts=up.get("reduce_occupancy_facts") or {},
        )
    if atom.startswith("select_repo_pr_refresh_gate_"):
        selected = up.get(f"select_occupancy_repo_{slot}") or {}
        inspected = up.get(f"inspect_repo_pr_refresh_{slot}") or {}
        return (
            inspected
            if selected.get("route") == "repo"
            else {"ok": True, "route": "empty", "slot": slot}
        )
    if atom.startswith("list_occupancy_pull_requests_"):
        from lokay.proc.list_occupancy_pull_requests import fetch

        return fetch(
            up.get(f"select_repo_pr_refresh_gate_{slot}") or {},
            config_path=config,
            live=live,
        )
    if atom.startswith("record_repo_pr_refresh_"):
        from lokay.proc.record_repo_pr_refresh import record

        return record(
            up.get(f"select_occupancy_repo_{slot}") or {},
            up.get(f"select_repo_pr_refresh_gate_{slot}") or {},
            up.get(f"list_occupancy_pull_requests_{slot}") or {},
        )
    if atom == "reduce_occupancy_refresh":
        from lokay.passkit.working import load_begin_working
        from lokay.proc.reduce_occupancy_refresh import reduce_state

        _, working = load_begin_working(pass_dir)
        results = [
            up.get(f"record_repo_pr_refresh_{i}") or {}
            for i in range(1, SLOT_COUNT + 1)
        ]
        return reduce_state(
            facts=up.get("reduce_occupancy_facts") or {},
            results=results,
            working=working,
        )
    if atom == "persist_occupancy_refresh":
        from lokay.proc.persist_occupancy_refresh import persist

        return persist(
            pass_dir=pass_dir, reduced=up.get("reduce_occupancy_refresh") or {}
        )
    if atom == "summarize_occupancy_refresh":
        from lokay.proc.summarize_occupancy_refresh import summarize

        return summarize(up.get("persist_occupancy_refresh") or {})
    return None

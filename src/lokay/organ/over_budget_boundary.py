"""Fala bindings for explicit bounded detached-worker budget slots."""

from typing import Any

SLOTS = 30


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def _stable(primary: dict, fallback: dict) -> dict:
    return dict(primary if primary.get("ok") else fallback)


def handle_over_budget(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "") or None
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    budget_s = int(inputs.get("budget_s") or 0)
    if atom == "prepare_over_budget_reap":
        from lokay.proc.prepare_over_budget_reap import prepare

        return prepare(pass_dir=pass_dir, budget_s=budget_s, slot_count=SLOTS)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    selected = up.get(f"select_budget_receipt_{slot}") or {}
    if atom.startswith("select_budget_receipt_"):
        from lokay.proc.select_budget_receipt_slot import select

        return select(up.get("prepare_over_budget_reap") or {}, slot=slot)
    if atom.startswith("inspect_budget_issue_state_"):
        from lokay.proc.inspect_budget_issue_state import inspect

        return inspect(selected, config_path=config, live=live)
    if atom.startswith("select_budget_issue_gate_"):
        inspected = up.get(f"inspect_budget_issue_state_{slot}") or {}
        return (
            {**inspected, "route": "check"}
            if selected.get("route") == "receipt"
            else dict(selected)
        )
    issue = up.get(f"select_budget_issue_gate_{slot}") or {}
    if atom.startswith("check_receipt_budget_"):
        from lokay.proc.check_receipt_budget import check

        return check(selected, issue, budget_s=budget_s)
    if atom.startswith("select_budget_check_gate_"):
        return _stable(up.get(f"check_receipt_budget_{slot}") or {}, selected)
    checked = up.get(f"select_budget_check_gate_{slot}") or {}
    if atom.startswith("inspect_budget_coder_"):
        from lokay.proc.inspect_budget_coder import inspect

        return inspect(checked)
    if atom.startswith("select_budget_coder_gate_"):
        return _stable(up.get(f"inspect_budget_coder_{slot}") or {}, checked)
    coder = up.get(f"select_budget_coder_gate_{slot}") or {}
    if atom.startswith("inspect_budget_coder_diff_"):
        from lokay.proc.inspect_budget_coder_diff import inspect

        return inspect(coder)
    if atom.startswith("select_budget_diff_gate_"):
        return _stable(up.get(f"inspect_budget_coder_diff_{slot}") or {}, coder)
    if atom.startswith("select_budget_receipt_route_"):
        from lokay.proc.select_budget_receipt_route import select

        return select(
            selected,
            issue,
            checked,
            coder,
            up.get(f"select_budget_diff_gate_{slot}") or {},
        )
    route = up.get(f"select_budget_receipt_route_{slot}") or {}
    if atom.startswith("commit_over_budget_diff_"):
        from lokay.proc.commit_over_budget_diff import commit

        return commit(route, config_path=config, live=live)
    if atom.startswith("select_budget_commit_outcome_"):
        return _stable(up.get(f"commit_over_budget_diff_{slot}") or {}, route)
    committed = up.get(f"select_budget_commit_outcome_{slot}") or {}
    if atom.startswith("push_over_budget_branch_"):
        from lokay.proc.push_over_budget_branch import push

        return push(committed, config_path=config, live=live)
    if atom.startswith("select_budget_push_outcome_"):
        return _stable(up.get(f"push_over_budget_branch_{slot}") or {}, committed)
    pushed = up.get(f"select_budget_push_outcome_{slot}") or {}
    if atom.startswith("create_over_budget_pr_"):
        from lokay.proc.create_over_budget_pr import create

        return create(pushed, config_path=config, live=live)
    if atom.startswith("select_budget_harvest_outcome_"):
        from lokay.proc.select_budget_harvest_outcome import select

        return select(
            route, committed, pushed, up.get(f"create_over_budget_pr_{slot}") or {}
        )
    harvest = up.get(f"select_budget_harvest_outcome_{slot}") or {}
    if atom.startswith("terminate_over_budget_worker_"):
        from lokay.proc.terminate_over_budget_worker import terminate

        return terminate(harvest)
    if atom.startswith("select_budget_termination_outcome_"):
        return _stable(up.get(f"terminate_over_budget_worker_{slot}") or {}, harvest)
    terminated = up.get(f"select_budget_termination_outcome_{slot}") or {}
    if atom.startswith("stamp_reaped_receipt_"):
        from lokay.proc.stamp_reaped_receipt import stamp

        return stamp(terminated)
    if atom.startswith("select_budget_stamp_outcome_"):
        outcome = _stable(up.get(f"stamp_reaped_receipt_{slot}") or {}, terminated)
        return {**outcome, "reason": str(outcome.get("reason") or "none")}
    stamped = up.get(f"select_budget_stamp_outcome_{slot}") or {}
    if atom.startswith("record_plan_only_failure_"):
        from lokay.proc.record_plan_only_failure import record

        return record(
            stamped,
            stuck_path=str((up.get("prepare_over_budget_reap") or {})["stuck_path"]),
        )
    if atom.startswith("select_plan_only_record_outcome_"):
        return _stable(up.get(f"record_plan_only_failure_{slot}") or {}, stamped)
    recorded = up.get(f"select_plan_only_record_outcome_{slot}") or {}
    if atom.startswith("park_plan_only_issue_"):
        from lokay.proc.park_plan_only_issue import park

        return park(recorded, config_path=config, live=live)
    if atom.startswith("record_budget_slot_outcome_"):
        from lokay.proc.record_budget_slot_outcome import record

        return record(
            selected,
            route,
            harvest,
            terminated,
            stamped,
            up.get(f"park_plan_only_issue_{slot}") or {},
        )
    if atom == "reduce_over_budget_reap":
        from lokay.proc.reduce_over_budget_reap import reduce_state

        return reduce_state(
            rows=[
                up.get(f"record_budget_slot_outcome_{i}") or {}
                for i in range(1, SLOTS + 1)
            ],
            budget_s=budget_s,
        )
    if atom == "summarize_over_budget_reap":
        from lokay.proc.summarize_over_budget_reap import summarize

        return summarize(up.get("reduce_over_budget_reap") or {})
    return None

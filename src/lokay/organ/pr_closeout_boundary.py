"""Fala bindings for authored PR-closeout slots and the one-PR path."""

from typing import Any


def handle_pr_closeout(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    selected = dict(inputs.get("selected") or {})
    if atom == "prepare_pr_closeout":
        from lokay.execution_contracts import CLOSEOUT_SLOT_COUNT
        from lokay.proc.prepare_pr_closeout import prepare

        return prepare(pass_dir=pass_dir, slot_count=CLOSEOUT_SLOT_COUNT)

    def _slot(name: str) -> int:
        suffix = name.rsplit("_", 1)[-1]
        return int(suffix) if suffix.isdigit() else 0

    slot = _slot(atom)
    if atom.startswith("select_pr_closeout_slot_"):
        from lokay.proc.select_pr_closeout_slot import select

        previous = up.get(f"record_pr_closeout_slot_{slot-1}") or {}
        return select(up.get("prepare_pr_closeout") or {}, previous, slot=slot)
    if atom.startswith("run_pr_closeout_slot_"):
        from lokay.proc.run_pr_closeout_slot import run

        return run(
            up.get(f"select_pr_closeout_slot_{slot}") or {},
            config_path=config,
            live=live,
        )
    if atom.startswith("record_pr_closeout_slot_"):
        from lokay.proc.record_pr_closeout_slot import record

        return record(
            up.get(f"select_pr_closeout_slot_{slot}") or {},
            up.get(f"run_pr_closeout_slot_{slot}") or {},
        )
    if atom == "reduce_pr_closeout":
        from lokay.execution_contracts import CLOSEOUT_SLOT_COUNT
        from lokay.proc.reduce_pr_closeout_slots import reduce

        return reduce(
            prepared=up.get("prepare_pr_closeout") or {},
            rows=[
                up.get(f"record_pr_closeout_slot_{i}") or {}
                for i in range(1, CLOSEOUT_SLOT_COUNT + 1)
            ],
            pass_dir=pass_dir,
        )
    if atom == "persist_pr_closeout":
        from lokay.proc.persist_pr_closeout import persist

        return persist(pass_dir=pass_dir, reduced=up.get("reduce_pr_closeout") or {})
    if atom == "summarize_pr_closeout":
        from lokay.proc.summarize_pr_closeout import summarize

        return summarize(up.get("persist_pr_closeout") or {})
    if atom == "inspect_closeout_pr":
        from lokay.proc.inspect_closeout_pr import inspect

        return inspect(selected)
    if atom == "read_closeout_issue":
        from lokay.proc.read_closeout_issue import read

        return read(up.get("inspect_closeout_pr") or {}, config_path=config)
    if atom == "classify_closeout_gate":
        from lokay.proc.classify_closeout_gate import classify

        return classify(
            up.get("inspect_closeout_pr") or {}, up.get("read_closeout_issue") or {}
        )
    if atom == "read_closeout_checks":
        from lokay.proc.read_closeout_checks import read

        return read(up.get("classify_closeout_gate") or {}, config_path=config)
    if atom == "route_closeout_checks":
        from lokay.proc.route_closeout_checks import route

        out = route(
            up.get("classify_closeout_gate") or {},
            up.get("read_closeout_checks") or {},
            live=live,
        )
        out["checks"] = dict((up.get("read_closeout_checks") or {}).get("checks") or {})
        return out
    if atom in {"authorize_closeout_repair", "authorize_closeout_review_repair"}:
        from lokay.proc.authorize_closeout_repair import authorize

        source = (
            up.get("route_closeout_checks")
            if atom == "authorize_closeout_repair"
            else up.get("classify_closeout_triage")
        )
        return authorize(up.get("classify_closeout_gate") or {}, source or {})
    if atom in {"run_closeout_repair", "run_closeout_review_repair"}:
        from lokay.proc.run_closeout_repair import repair

        auth = (
            "authorize_closeout_repair"
            if atom == "run_closeout_repair"
            else "authorize_closeout_review_repair"
        )
        return repair(
            up.get("classify_closeout_gate") or {},
            up.get(auth) or {},
            config_path=config,
        )
    if atom == "run_closeout_triage":
        from lokay.proc.run_closeout_triage import triage

        return triage(up.get("classify_closeout_gate") or {}, config_path=config)
    if atom == "classify_closeout_triage":
        from lokay.proc.classify_closeout_triage import classify

        return classify(up.get("run_closeout_triage") or {})
    if atom == "select_closeout_repair_result":
        from lokay.proc.select_closeout_repair_result import select

        first = select(
            up.get("authorize_closeout_repair") or {},
            up.get("run_closeout_repair") or {},
        )
        return (
            select(
                up.get("authorize_closeout_review_repair") or {},
                up.get("run_closeout_review_repair") or {},
            )
            if (up.get("authorize_closeout_review_repair") or {}).get("route")
            == "repair"
            else first
        )
    if atom in {"park_closed_pr_issue", "park_delivered_pr_issue"}:
        from lokay.proc.park_closeout_issue import park

        return park(
            up.get("classify_closeout_gate") or {}, config_path=config, live=live
        )
    if atom == "select_closeout_park_result":
        delivered = up.get("park_delivered_pr_issue") or {}
        closed = up.get("park_closed_pr_issue") or {}
        return (
            delivered
            if delivered.get("ok")
            else closed if closed.get("ok") else {"ok": True, "applied": False}
        )
    if atom == "build_closeout_evidence":
        from lokay.proc.build_closeout_evidence import build

        return build(
            up.get("classify_closeout_gate") or {},
            up.get("route_closeout_checks") or {},
            up.get("classify_closeout_triage") or {},
            up.get("select_closeout_repair_result") or {},
            up.get("select_closeout_park_result") or {},
        )
    if atom == "finalize_closeout_pr":
        from lokay.proc.finalize_closeout_pr import finalize

        return finalize(
            up.get("classify_closeout_gate") or {},
            up.get("route_closeout_checks") or {},
            up.get("classify_closeout_triage") or {},
            up.get("select_closeout_repair_result") or {},
            up.get("build_closeout_evidence") or {},
        )
    if atom == "summarize_closeout_pr":
        from lokay.proc.summarize_closeout_pr import summarize

        return summarize(up.get("finalize_closeout_pr") or {})
    return None

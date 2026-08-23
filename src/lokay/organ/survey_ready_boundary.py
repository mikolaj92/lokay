"""Fala bindings for the explicit ready-survey repository slots."""

from typing import Any

SLOT_COUNT = 30


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def handle_survey_ready(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_ready_survey":
        from lokay.proc.prepare_ready_survey import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    if atom.startswith("select_ready_repo_"):
        from lokay.proc.select_ready_repo_slot import select

        return select(up.get("prepare_ready_survey") or {}, slot=_slot(atom))
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("list_work_ready_"):
        from lokay.proc.list_work_ready_issues import fetch

        return fetch(
            up.get(f"select_ready_repo_{slot}") or {}, config_path=config, live=live
        )
    if atom.startswith("classify_ready_repo_"):
        from lokay.proc.classify_ready_repo_issues import classify

        return classify(
            pass_dir=pass_dir,
            selected=up.get(f"select_ready_repo_{slot}") or {},
            listed=up.get(f"list_work_ready_{slot}") or {},
        )
    if atom.startswith("park_blocked_ready_"):
        from lokay.proc.park_one_blocked_ready_issue import park

        return park(
            up.get(f"classify_ready_repo_{slot}") or {}, config_path=config, live=live
        )
    if atom.startswith("record_ready_repo_"):
        from lokay.proc.record_ready_repo_result import record

        return record(
            up.get(f"select_ready_repo_{slot}") or {},
            up.get(f"classify_ready_repo_{slot}") or {},
            up.get(f"park_blocked_ready_{slot}") or {},
        )
    if atom == "reduce_ready_survey":
        from lokay.passkit.working import load_begin_working
        from lokay.proc.reduce_ready_survey import reduce_state

        _, working = load_begin_working(pass_dir)
        results = [
            up.get(f"record_ready_repo_{i}") or {} for i in range(1, SLOT_COUNT + 1)
        ]
        return reduce_state(
            prepared=up.get("prepare_ready_survey") or {},
            results=results,
            working=working,
        )
    if atom == "finalize_ready_survey":
        from lokay.proc.finalize_ready_survey import finalize

        return finalize(pass_dir=pass_dir, reduced=up.get("reduce_ready_survey") or {})
    if atom == "update_ready_survey_stamp":
        from lokay.proc.update_ready_survey_stamp import update

        return update(
            pass_dir=pass_dir, finalized=up.get("finalize_ready_survey") or {}
        )
    return None

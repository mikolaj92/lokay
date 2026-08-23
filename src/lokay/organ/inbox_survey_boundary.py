"""Fala bindings for explicit inbox-survey repository slots."""

from typing import Any

SLOTS = 30


def _slot(atom):
    return int(atom.rsplit("_", 1)[1])


def handle_inbox_survey(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_inbox_survey":
        from lokay.proc.prepare_inbox_survey import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOTS)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_inbox_repo_"):
        from lokay.proc.select_inbox_repo_slot import select

        return select(up.get("prepare_inbox_survey") or {}, slot=slot)
    if atom.startswith("list_inbox_repo_"):
        from lokay.proc.list_inbox_repo_issues import fetch

        return fetch(
            up.get(f"select_inbox_repo_{slot}") or {}, config_path=config, live=live
        )
    if atom.startswith("classify_inbox_repo_"):
        from lokay.proc.classify_inbox_repo_issues import classify

        return classify(
            up.get("prepare_inbox_survey") or {},
            up.get(f"select_inbox_repo_{slot}") or {},
            up.get(f"list_inbox_repo_{slot}") or {},
        )
    if atom.startswith("record_inbox_repo_"):
        from lokay.proc.record_inbox_repo_result import record

        return record(
            up.get("prepare_inbox_survey") or {},
            up.get(f"select_inbox_repo_{slot}") or {},
            up.get(f"classify_inbox_repo_{slot}") or {},
        )
    if atom == "reduce_inbox_survey":
        from lokay.passkit.working import load_begin_working
        from lokay.proc.reduce_inbox_survey import reduce_state

        _, working = load_begin_working(pass_dir)
        return reduce_state(
            prepared=up.get("prepare_inbox_survey") or {},
            rows=[up.get(f"record_inbox_repo_{i}") or {} for i in range(1, SLOTS + 1)],
            working=working,
        )
    if atom == "persist_inbox_survey":
        from lokay.proc.persist_inbox_survey import persist

        return persist(pass_dir=pass_dir, reduced=up.get("reduce_inbox_survey") or {})
    if atom == "update_inbox_survey_stamp":
        from lokay.proc.update_inbox_survey_stamp import update

        return update(pass_dir=pass_dir, persisted=up.get("persist_inbox_survey") or {})
    return None

"""Fala bindings for explicit PR-survey repository slots."""

from typing import Any

SLOTS = 30


def _slot(atom):
    return int(atom.rsplit("_", 1)[1])


def handle_pr_survey(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_pr_survey":
        from lokay.proc.prepare_pr_survey import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOTS)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_pr_survey_repo_"):
        from lokay.proc.select_pr_survey_slot import select

        return select(up.get("prepare_pr_survey") or {}, slot=slot)
    if atom.startswith("list_pr_survey_repo_"):
        from lokay.proc.list_pr_survey_repo import fetch

        return fetch(
            up.get(f"select_pr_survey_repo_{slot}") or {}, config_path=config, live=live
        )
    if atom.startswith("classify_pr_survey_repo_"):
        from lokay.proc.classify_pr_survey_repo import classify

        return classify(
            up.get(f"select_pr_survey_repo_{slot}") or {},
            up.get(f"list_pr_survey_repo_{slot}") or {},
        )
    if atom.startswith("record_pr_survey_repo_"):
        from lokay.proc.record_pr_survey_repo import record

        return record(
            up.get("prepare_pr_survey") or {},
            up.get(f"select_pr_survey_repo_{slot}") or {},
            up.get(f"classify_pr_survey_repo_{slot}") or {},
        )
    if atom == "reduce_pr_survey":
        from lokay.passkit.working import load_begin_working
        from lokay.proc.reduce_pr_survey import reduce_state

        _, working = load_begin_working(pass_dir)
        return reduce_state(
            prepared=up.get("prepare_pr_survey") or {},
            rows=[
                up.get(f"record_pr_survey_repo_{i}") or {} for i in range(1, SLOTS + 1)
            ],
            working=working,
        )
    if atom == "persist_pr_survey":
        from lokay.proc.persist_pr_survey import persist

        return persist(pass_dir=pass_dir, reduced=up.get("reduce_pr_survey") or {})
    if atom == "update_pr_survey_stamp":
        from lokay.proc.update_pr_survey_stamp import update

        return update(pass_dir=pass_dir, persisted=up.get("persist_pr_survey") or {})
    return None

"""Fala bindings for explicit ready-hygiene repository and issue slots."""

from typing import Any

REPO_SLOTS = CANDIDATE_SLOTS = 30


def _slot(atom):
    return int(atom.rsplit("_", 1)[1])


def handle_ready_hygiene(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_ready_hygiene":
        from lokay.proc.prepare_ready_hygiene import prepare

        return prepare(config_path=config, live=live, slot_count=REPO_SLOTS)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_ready_hygiene_repo_"):
        from lokay.proc.select_ready_hygiene_repo import select

        return select(up.get("prepare_ready_hygiene") or {}, slot=slot)
    if atom.startswith("list_ready_hygiene_repo_"):
        from lokay.proc.list_ready_hygiene_issues import fetch

        return fetch(
            up.get(f"select_ready_hygiene_repo_{slot}") or {},
            config_path=config,
            live=live,
        )
    if atom.startswith("classify_ready_hygiene_repo_"):
        from lokay.proc.classify_ready_hygiene_issues import classify

        return classify(
            up.get(f"select_ready_hygiene_repo_{slot}") or {},
            up.get(f"list_ready_hygiene_repo_{slot}") or {},
        )
    if atom.startswith("record_ready_hygiene_repo_"):
        from lokay.proc.record_ready_hygiene_repo import record

        return record(
            up.get(f"select_ready_hygiene_repo_{slot}") or {},
            up.get(f"classify_ready_hygiene_repo_{slot}") or {},
        )
    if atom == "reduce_ready_hygiene_candidates":
        from lokay.proc.reduce_ready_hygiene_candidates import reduce_candidates

        return reduce_candidates(
            up.get("prepare_ready_hygiene") or {},
            [
                up.get(f"record_ready_hygiene_repo_{i}") or {}
                for i in range(1, REPO_SLOTS + 1)
            ],
            slot_count=CANDIDATE_SLOTS,
        )
    if atom.startswith("select_ready_hygiene_candidate_"):
        from lokay.proc.select_ready_hygiene_candidate import select

        return select(up.get("reduce_ready_hygiene_candidates") or {}, slot=slot)
    if atom.startswith("remove_ready_hygiene_candidate_"):
        from lokay.proc.remove_ready_hygiene_label import remove

        return remove(
            up.get(f"select_ready_hygiene_candidate_{slot}") or {}, config_path=config
        )
    if atom.startswith("record_ready_hygiene_candidate_"):
        from lokay.proc.record_ready_hygiene_candidate import record

        return record(
            up.get(f"select_ready_hygiene_candidate_{slot}") or {},
            up.get(f"remove_ready_hygiene_candidate_{slot}") or {},
        )
    if atom == "reduce_ready_hygiene":
        from lokay.proc.reduce_ready_hygiene import reduce_state

        return reduce_state(
            up.get("prepare_ready_hygiene") or {},
            up.get("reduce_ready_hygiene_candidates") or {},
            [
                up.get(f"record_ready_hygiene_candidate_{i}") or {}
                for i in range(1, CANDIDATE_SLOTS + 1)
            ],
        )
    if atom == "update_ready_hygiene_stamp":
        from lokay.proc.update_ready_hygiene_stamp import update

        return update(up.get("reduce_ready_hygiene") or {}, config_path=config)
    return None

"""Fala bindings for explicit leftover-closeout repository, label, and issue slots."""

from typing import Any

REPO_SLOTS = CANDIDATE_SLOTS = 30


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def handle_leftover_closeout(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom == "prepare_leftover_closeout":
        from lokay.proc.prepare_leftover_closeout import prepare

        return prepare(config_path=config, live=live, slot_count=REPO_SLOTS)
    if atom.startswith("select_leftover_repo_"):
        from lokay.proc.select_leftover_repo import select

        return select(up.get("prepare_leftover_closeout") or {}, slot=slot)
    if atom.startswith("select_leftover_label_"):
        from lokay.proc.select_leftover_label import select

        repo_slot = int(atom.split("_")[-2])
        previous = up.get(f"record_leftover_label_{repo_slot}_{slot-1}") or {}
        return select(
            up.get(f"select_leftover_repo_{repo_slot}") or {}, previous, slot=slot
        )
    if atom.startswith("list_leftover_label_"):
        from lokay.proc.list_leftover_closed_ready import fetch

        repo_slot = int(atom.split("_")[-2])
        return fetch(
            up.get(f"select_leftover_label_{repo_slot}_{slot}") or {},
            config_path=config,
            live=live,
        )
    if atom.startswith("classify_leftover_label_"):
        from lokay.proc.classify_leftover_probe import classify

        repo_slot = int(atom.split("_")[-2])
        return classify(
            up.get(f"select_leftover_label_{repo_slot}_{slot}") or {},
            up.get(f"list_leftover_label_{repo_slot}_{slot}") or {},
        )
    if atom.startswith("record_leftover_label_"):
        from lokay.proc.record_leftover_label import record

        repo_slot = int(atom.split("_")[-2])
        return record(
            up.get(f"select_leftover_label_{repo_slot}_{slot}") or {},
            up.get(f"classify_leftover_label_{repo_slot}_{slot}") or {},
        )
    if atom.startswith("record_leftover_repo_"):
        from lokay.proc.record_leftover_repo import record

        return record(
            up.get(f"select_leftover_repo_{slot}") or {},
            [up.get(f"record_leftover_label_{slot}_{i}") or {} for i in (1, 2)],
        )
    if atom == "reduce_leftover_candidates":
        from lokay.proc.reduce_leftover_candidates import reduce_candidates

        return reduce_candidates(
            up.get("prepare_leftover_closeout") or {},
            [
                up.get(f"record_leftover_repo_{i}") or {}
                for i in range(1, REPO_SLOTS + 1)
            ],
            slot_count=CANDIDATE_SLOTS,
        )
    if atom.startswith("select_leftover_candidate_"):
        from lokay.proc.select_leftover_candidate import select

        return select(up.get("reduce_leftover_candidates") or {}, slot=slot)
    if atom.startswith("park_leftover_candidate_"):
        from lokay.proc.park_leftover_candidate import park

        return park(
            up.get(f"select_leftover_candidate_{slot}") or {}, config_path=config
        )
    if atom.startswith("record_leftover_candidate_"):
        from lokay.proc.record_leftover_candidate import record

        return record(
            up.get(f"select_leftover_candidate_{slot}") or {},
            up.get(f"park_leftover_candidate_{slot}") or {},
        )
    if atom == "reduce_leftover_closeout":
        from lokay.proc.reduce_leftover_closeout import reduce_state

        return reduce_state(
            up.get("prepare_leftover_closeout") or {},
            up.get("reduce_leftover_candidates") or {},
            [
                up.get(f"record_leftover_candidate_{i}") or {}
                for i in range(1, CANDIDATE_SLOTS + 1)
            ],
        )
    if atom == "update_leftover_stamp":
        from lokay.proc.update_leftover_stamp import update

        return update(up.get("reduce_leftover_closeout") or {}, config_path=config)
    return None

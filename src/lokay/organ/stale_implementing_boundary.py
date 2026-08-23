"""Fala bindings for explicit stale-stage repository and candidate slots."""

from typing import Any

REPO_SLOTS = 30
CANDIDATE_SLOTS = 120
LABELS = ("ai:ci-waiting", "ai:in-progress", "ai:pr-open", "ai:repairing")


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def handle_stale_implementing(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "") or None
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_stale_implementing_reap":
        from lokay.proc.prepare_stale_implementing_reap import prepare

        return prepare(pass_dir=pass_dir, config_path=config, slot_count=REPO_SLOTS)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_stale_repo_"):
        from lokay.proc.select_stale_repo_slot import select

        return select(up.get("prepare_stale_implementing_reap") or {}, slot=slot)
    if atom.startswith("list_stale_repo_"):
        from lokay.proc.list_stale_implementing_issues import fetch

        label_index = int(atom.split("_label_")[1].split("_")[0])
        return fetch(
            up.get(f"select_stale_repo_{slot}") or {},
            config_path=config,
            live=live,
            label=LABELS[label_index - 1],
        )
    if atom.startswith("reduce_stale_repo_"):
        from lokay.proc.reduce_stale_repo_probe import reduce_state

        rows = [up.get(f"list_stale_repo_label_{j}_{slot}") or {} for j in range(1, 5)]
        return reduce_state(up.get(f"select_stale_repo_{slot}") or {}, rows)
    if atom == "reduce_stale_implementing_probe":
        from lokay.proc.reduce_stale_implementing_probe import reduce_state

        rows = [
            up.get(f"reduce_stale_repo_{i}") or {} for i in range(1, REPO_SLOTS + 1)
        ]
        return reduce_state(
            prepared=up.get("prepare_stale_implementing_reap") or {},
            rows=rows,
            candidate_slots=CANDIDATE_SLOTS,
        )
    if atom == "check_stale_mutation_gate":
        from lokay.proc.check_stale_mutation_gate import check

        return check(
            up.get("reduce_stale_implementing_probe") or {},
            config_path=config,
            live=live,
        )
    if atom.startswith("select_stale_candidate_"):
        from lokay.proc.select_stale_candidate_slot import select

        return select(
            up.get("reduce_stale_implementing_probe") or {},
            up.get("check_stale_mutation_gate") or {},
            slot=slot,
        )
    if atom.startswith("restore_stale_issue_ready_"):
        from lokay.proc.restore_stale_issue_ready import restore

        return restore(
            up.get(f"select_stale_candidate_{slot}") or {},
            config_path=config,
            live=live,
        )
    if atom.startswith("record_stale_candidate_"):
        from lokay.proc.record_stale_candidate_outcome import record

        return record(
            up.get(f"select_stale_candidate_{slot}") or {},
            up.get(f"restore_stale_issue_ready_{slot}") or {},
        )
    if atom == "reduce_stale_reap_effects":
        from lokay.proc.reduce_stale_reap_effects import reduce_state

        rows = [
            up.get(f"record_stale_candidate_{i}") or {}
            for i in range(1, CANDIDATE_SLOTS + 1)
        ]
        return reduce_state(
            probe=up.get("reduce_stale_implementing_probe") or {},
            gate=up.get("check_stale_mutation_gate") or {},
            rows=rows,
        )
    if atom == "update_stale_empty_stamp":
        from lokay.proc.update_stale_empty_stamp import update

        return update(up.get("reduce_stale_reap_effects") or {})
    if atom == "persist_stale_implementing_reap":
        from lokay.proc.persist_stale_implementing_reap import persist

        return persist(up.get("update_stale_empty_stamp") or {})
    if atom == "summarize_stale_implementing_reap":
        from lokay.proc.summarize_stale_implementing_reap import summarize

        return summarize(
            up.get("prepare_stale_implementing_reap") or {},
            up.get("persist_stale_implementing_reap") or {},
        )
    return None

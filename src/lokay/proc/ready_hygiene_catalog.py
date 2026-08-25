"""Probe and clean the whole ready-hygiene catalog in one atom (no 30-slot unroll)."""

from __future__ import annotations

CANDIDATE_SLOTS = 30


def run(prepared: dict, *, config_path: str | None, live: bool) -> dict:
    from lokay.proc.classify_ready_hygiene_issues import classify
    from lokay.proc.list_ready_hygiene_issues import fetch
    from lokay.proc.record_ready_hygiene_candidate import record as record_candidate
    from lokay.proc.record_ready_hygiene_repo import record as record_repo
    from lokay.proc.reduce_ready_hygiene import reduce_state
    from lokay.proc.reduce_ready_hygiene_candidates import reduce_candidates
    from lokay.proc.remove_ready_hygiene_label import remove
    from lokay.proc.select_ready_hygiene_candidate import select as select_candidate
    from lokay.proc.select_ready_hygiene_repo import select as select_repo

    repos = list(prepared.get("repos") or [])
    rows = []
    if prepared.get("route") != "skip":
        for slot in range(1, len(repos) + 1):
            selected = select_repo(prepared, slot=slot)
            listed = {}
            if selected.get("route") == "probe":
                listed = fetch(selected, config_path=config_path, live=live)
            rows.append(record_repo(selected, classify(selected, listed)))
    candidates = reduce_candidates(prepared, rows, slot_count=CANDIDATE_SLOTS)
    if not candidates.get("ok"):
        return candidates
    cand_rows = []
    for slot in range(1, len(list(candidates.get("candidates") or [])) + 1):
        selected = select_candidate(candidates, slot=slot)
        removed = {}
        if selected.get("route") == "remove":
            removed = remove(selected, config_path=config_path)
        cand_rows.append(record_candidate(selected, removed))
    return reduce_state(prepared, candidates, cand_rows)

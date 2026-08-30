"""Park the whole leftover CLOSED-ready catalog in one atom (no 30-slot unroll)."""

from __future__ import annotations

REPO_SLOTS = CANDIDATE_SLOTS = 30


def _one_repo(
    prepared: dict, *, slot: int, config_path: str | None, live: bool
) -> dict:
    from lokay.proc.classify_leftover_probe import classify
    from lokay.proc.list_leftover_closed_ready import fetch
    from lokay.proc.record_leftover_label import record as record_label
    from lokay.proc.record_leftover_repo import record as record_repo
    from lokay.proc.select_leftover_label import select as select_label
    from lokay.proc.select_leftover_repo import select as select_repo

    selected = select_repo(prepared, slot=slot)
    if selected.get("route") != "labels":
        return record_repo(selected, [])
    rows = []
    previous = {}
    for label_slot in (1, 2):
        label = select_label(selected, previous, slot=label_slot)
        listed = {}
        if label.get("route") == "probe":
            listed = fetch(label, config_path=config_path, live=live)
        previous = record_label(label, classify(label, listed))
        rows.append(previous)
        if previous.get("route") == "failed":
            break
    return record_repo(selected, rows)


def _one_candidate(candidates: dict, *, slot: int, config_path: str | None) -> dict:
    from lokay.proc.park_leftover_candidate import park
    from lokay.proc.record_leftover_candidate import record
    from lokay.proc.select_leftover_candidate import select

    selected = select(candidates, slot=slot)
    parked = {}
    if selected.get("route") == "park":
        parked = park(selected, config_path=config_path)
        if not parked.get("ok"):
            return parked
    return record(selected, parked)


def run(prepared: dict, *, config_path: str | None, live: bool) -> dict:
    from lokay.proc.reduce_leftover_candidates import reduce_candidates
    from lokay.proc.reduce_leftover_closeout import reduce_state

    if not prepared.get("ok"):
        return dict(prepared)
    repos = list(prepared.get("repos") or [])
    rows = []
    if prepared.get("route") != "skip":
        rows = [
            _one_repo(prepared, slot=slot, config_path=config_path, live=live)
            for slot in range(1, len(repos) + 1)
        ]
    candidates = reduce_candidates(prepared, rows, slot_count=CANDIDATE_SLOTS)
    if not candidates.get("ok"):
        return candidates
    if prepared.get("route") == "skip" and not list(candidates.get("candidates") or []):
        return reduce_state(prepared, candidates, [])
    cand_rows = []
    for slot in range(1, len(list(candidates.get("candidates") or [])) + 1):
        recorded = _one_candidate(candidates, slot=slot, config_path=config_path)
        if not recorded.get("ok"):
            return recorded
        cand_rows.append(recorded)
    reduced = reduce_state(prepared, candidates, cand_rows)
    if candidates.get("leftover_skip"):
        reduced["leftover_skip"] = True
        reduced["leftover_overflow"] = True
        reduced["reason"] = candidates.get("reason") or "leftover_overflow"
        reduced["count"] = candidates.get("count")
        reduced["slot_count"] = candidates.get("slot_count")
    return reduced

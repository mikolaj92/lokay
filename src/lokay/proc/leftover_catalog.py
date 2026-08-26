"""Park the whole leftover CLOSED-ready catalog in one atom (no 30-slot unroll).

Overflow and leftover-probe failure skip leftover. They must not fail the
closeout path or send the daemon into recovery_mill.
"""

from __future__ import annotations

REPO_SLOTS = CANDIDATE_SLOTS = 30


def skip(*, reason: str, extra: dict | None = None) -> dict:
    """Fail-closed leftover skip: leftover is not work; host the factory."""
    out = {
        "ok": True,
        "route": "skip",
        "skipped": True,
        "reason": reason,
        "leftover_closed": 0,
        "labels_removed": False,
        "issue_to_pr_started": 0,
        "closed_out": [],
        "planned": True,
        "applied": False,
        "probe_failed": reason != "recent_empty",
        "failed_repos": list((extra or {}).get("failed_repos") or []),
    }
    if extra:
        for key in ("error", "count", "slot_count"):
            if extra.get(key) is not None:
                out[key] = extra[key]
    return out


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


def _candidate_count(rows: list[dict]) -> int:
    seen = set()
    for row in rows:
        for item in row.get("candidates") or []:
            seen.add((str(item.get("repo") or ""), int(item.get("number") or 0)))
    return len(seen)


def run(prepared: dict, *, config_path: str | None, live: bool) -> dict:
    from lokay.proc.reduce_leftover_candidates import reduce_candidates
    from lokay.proc.reduce_leftover_closeout import reduce_state

    if not prepared.get("ok"):
        return skip(
            reason="prepare_failed",
            extra={
                "error": prepared.get("error") or "leftover prepare failed",
                "count": prepared.get("count"),
                "slot_count": prepared.get("slot_count"),
            },
        )
    repos = list(prepared.get("repos") or [])
    if len(repos) > REPO_SLOTS:
        return skip(
            reason="catalog_exceeds_slots",
            extra={
                "error": "leftover closeout catalog exceeds authored slots",
                "count": len(repos),
                "slot_count": REPO_SLOTS,
            },
        )
    rows = []
    if prepared.get("route") != "skip":
        for slot in range(1, len(repos) + 1):
            row = _one_repo(prepared, slot=slot, config_path=config_path, live=live)
            rows.append(row)
            if row.get("route") == "failed":
                return skip(
                    reason="leftover_probe_failed",
                    extra={
                        "error": row.get("error") or "leftover-probe failed",
                        "failed_repos": [str(row.get("repo") or "")],
                    },
                )
            if _candidate_count(rows) > CANDIDATE_SLOTS:
                return skip(
                    reason="candidates_exceed_slots",
                    extra={
                        "error": "leftover closeout candidates exceed authored slots",
                        "count": _candidate_count(rows),
                        "slot_count": CANDIDATE_SLOTS,
                    },
                )
    candidates = reduce_candidates(prepared, rows, slot_count=CANDIDATE_SLOTS)
    if not candidates.get("ok"):
        return skip(
            reason="candidates_exceed_slots",
            extra={
                "error": candidates.get("error")
                or "leftover closeout candidates exceed authored slots",
                "count": candidates.get("count"),
                "slot_count": candidates.get("slot_count"),
            },
        )
    cand_rows = []
    for slot in range(1, len(list(candidates.get("candidates") or [])) + 1):
        recorded = _one_candidate(candidates, slot=slot, config_path=config_path)
        if not recorded.get("ok"):
            return skip(
                reason="leftover_park_failed",
                extra={"error": recorded.get("error") or "leftover park failed"},
            )
        cand_rows.append(recorded)
    return reduce_state(prepared, candidates, cand_rows)

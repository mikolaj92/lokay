"""Survey the whole inbox catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations


def run(
    prepared: dict, *, pass_dir: str, config_path: str | None, live: bool
) -> dict:
    from lokay.passkit.working import load_begin_working
    from lokay.proc.classify_inbox_repo_issues import classify
    from lokay.proc.list_inbox_repo_issues import fetch
    from lokay.proc.persist_inbox_survey import persist
    from lokay.proc.record_inbox_repo_result import record
    from lokay.proc.reduce_inbox_survey import reduce_state
    from lokay.proc.select_inbox_repo_slot import select

    _, working = load_begin_working(pass_dir)
    repos = list(prepared.get("repos") or [])
    rows = []
    for slot in range(1, len(repos) + 1):
        selected = select(prepared, slot=slot)
        listed = {}
        if selected.get("route") == "survey":
            listed = fetch(selected, config_path=config_path, live=live)
        classified = classify(prepared, selected, listed)
        rows.append(record(prepared, selected, classified))
    reduced = reduce_state(prepared=prepared, rows=rows, working=working)
    return persist(pass_dir=pass_dir, reduced=reduced)

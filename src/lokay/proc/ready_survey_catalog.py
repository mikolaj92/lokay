"""Survey the whole ready catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations


def run(
    prepared: dict, *, pass_dir: str, config_path: str | None, live: bool
) -> dict:
    from lokay.passkit.working import load_begin_working
    from lokay.proc.classify_ready_repo_issues import classify
    from lokay.proc.finalize_ready_survey import finalize
    from lokay.proc.list_work_ready_issues import fetch
    from lokay.proc.park_one_blocked_ready_issue import park
    from lokay.proc.record_ready_repo_result import record
    from lokay.proc.reduce_ready_survey import reduce_state
    from lokay.proc.select_ready_repo_slot import select

    _, working = load_begin_working(pass_dir)
    if prepared.get("route") != "skip" and not prepared.get("recent_empty"):
        from lokay.proc.dual_ready_catalog import run as wake_catalog
        from lokay.proc.reduce_dual_ready_catalog import apply_wake

        wake = wake_catalog(
            prepared, config_path=config_path, live=live, working=working
        )
        if not wake.get("ok"):
            return wake
        prepared = apply_wake(prepared, wake)
        working = {
            **working,
            "dual_ready_wake_repos": list(wake.get("wake_repos") or []),
        }
    repos = list(prepared.get("repos") or [])
    results = []
    if prepared.get("route") != "skip":
        for slot in range(1, len(repos) + 1):
            selected = select(prepared, slot=slot)
            listed = {}
            parked = {}
            if selected.get("route") == "survey":
                listed = fetch(selected, config_path=config_path, live=live)
            classified = classify(
                pass_dir=pass_dir, selected=selected, listed=listed
            )
            if classified.get("route") == "blocked":
                parked = park(classified, config_path=config_path, live=live)
            results.append(record(selected, classified, parked))
    reduced = reduce_state(prepared=prepared, results=results, working=working)
    return finalize(pass_dir=pass_dir, reduced=reduced)

"""Reap the whole stale-implementing catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations

REPO_SLOTS = 30
CANDIDATE_SLOTS = 120
LABELS = ("ai:ci-waiting", "ai:in-progress", "ai:pr-open", "ai:repairing")


def _one_repo(
    prepared: dict, *, slot: int, config_path: str | None, live: bool
) -> dict:
    from lokay.proc.list_stale_implementing_issues import fetch
    from lokay.proc.reduce_stale_repo_probe import reduce_state
    from lokay.proc.select_stale_repo_slot import select

    selected = select(prepared, slot=slot)
    if selected.get("route") != "repo":
        return reduce_state(selected, [])
    rows = [
        fetch(selected, config_path=config_path, live=live, label=label)
        for label in LABELS
    ]
    return reduce_state(selected, rows)


def _one_candidate(
    probe: dict,
    gate: dict,
    *,
    slot: int,
    config_path: str | None,
    live: bool,
) -> dict:
    from lokay.proc.record_stale_candidate_outcome import record
    from lokay.proc.restore_stale_issue_ready import restore
    from lokay.proc.select_stale_candidate_slot import select

    selected = select(probe, gate, slot=slot)
    restored = {}
    if selected.get("route") == "apply":
        restored = restore(selected, config_path=config_path, live=live)
    return record(selected, restored)


def run(prepared: dict, *, config_path: str | None, live: bool) -> dict:
    from lokay.proc.check_stale_mutation_gate import check
    from lokay.proc.reduce_stale_implementing_probe import reduce_state as reduce_probe
    from lokay.proc.reduce_stale_reap_effects import reduce_state as reduce_effects
    from lokay.proc.update_stale_empty_stamp import update

    if not prepared.get("ok"):
        return dict(prepared)
    repos = list(prepared.get("repos") or [])
    if len(repos) > REPO_SLOTS:
        return {
            "ok": False,
            "error": "stale implementing catalog exceeds authored slots",
            "repos": len(repos),
            "slot_count": REPO_SLOTS,
        }
    repo_rows = []
    if prepared.get("route") == "probe":
        repo_rows = [
            _one_repo(prepared, slot=slot, config_path=config_path, live=live)
            for slot in range(1, len(repos) + 1)
        ]
    probe = reduce_probe(
        prepared=prepared, rows=repo_rows, candidate_slots=CANDIDATE_SLOTS
    )
    if not probe.get("ok"):
        return dict(probe)
    gate = check(probe, config_path=config_path, live=live)
    candidates = list(probe.get("candidates") or [])
    candidate_rows = [
        _one_candidate(
            probe, gate, slot=slot, config_path=config_path, live=live
        )
        for slot in range(1, len(candidates) + 1)
    ]
    return update(reduce_effects(probe=probe, gate=gate, rows=candidate_rows))

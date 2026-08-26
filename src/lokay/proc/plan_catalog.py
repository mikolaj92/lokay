"""Build the whole pass-plan catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations


def run(prepared: dict, *, pass_dir: str) -> dict:
    from lokay.passkit import io as pass_io
    from lokay.proc.build_repo_plan_fragment import build
    from lokay.proc.record_repo_plan_fragment import record
    from lokay.proc.reduce_pass_plan import reduce_state
    from lokay.proc.select_plan_repo_slot import select

    if not prepared.get("ok"):
        return dict(prepared)
    repos = list(prepared.get("repos") or [])
    fragments = []
    for slot in range(1, len(repos) + 1):
        selected = select(prepared, slot=slot)
        fragment = {}
        if selected.get("route") == "repo":
            fragment = build(
                pass_dir=pass_dir, prepared=prepared, selected=selected
            )
        fragments.append(record(selected, fragment))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    return reduce_state(
        prepared=prepared, fragments=fragments, working=working
    )

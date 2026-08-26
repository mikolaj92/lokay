"""Re-select the next implementable catalog row after a parked queue-conflict.

One needs_human / skip / close must not empty clean_repos while another
product candidate remains implementable.
"""

from __future__ import annotations

PARK_ROUTES = frozenset({"needs_human", "skip", "close"})


def run(*, pass_dir: str, recorded: dict) -> dict:
    from lokay.organ.implementation_selection_boundary import SLOT_COUNT
    from lokay.passkit import io as pass_io
    from lokay.proc.implementation_selection_catalog import run as catalog
    from lokay.proc.persist_implementation_selection import persist
    from lokay.proc.prepare_implementation_selection import prepare
    from lokay.proc.select_queue_conflict_candidate import select

    route = str(recorded.get("route") or "none")
    if route not in PARK_ROUTES:
        implement = pass_io.read_json(pass_io.implement_path(pass_dir))
        return {
            "ok": True,
            "route": route,
            "advanced": False,
            "clean_repos": list(implement.get("clean_repos") or []),
        }
    prepared = prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    if not prepared.get("ok"):
        return dict(prepared)
    reduced = catalog(prepared, pass_dir=pass_dir)
    if not reduced.get("ok"):
        return dict(reduced)
    persist(pass_dir=pass_dir, reduced=reduced)
    nxt = select(pass_dir=pass_dir)
    return {
        "ok": True,
        "route": str(nxt.get("route") or "none"),
        "advanced": True,
        "clean_repos": list(reduced.get("clean_repos") or []),
        "repo": nxt.get("repo"),
        "issue": nxt.get("issue"),
        "candidate": nxt.get("candidate"),
    }

"""Harvest the whole CLOSED catalog in one atom (no 30-slot Fala unroll)."""


def harvest(facts: dict) -> dict:
    from lokay.proc.probe_harvest_closed_repo import probe
    from lokay.proc.record_harvest_catalog_slot import record
    from lokay.proc.select_harvest_catalog_slot import select

    out = dict(facts)
    repos = list(out.get("repos") or [])
    for slot in range(1, len(repos) + 1):
        selected = select(out, slot=slot)
        probed = {}
        if selected.get("harvest_route") == "probe":
            probed = probe(selected)
        out = record(selected, probed)
    return out

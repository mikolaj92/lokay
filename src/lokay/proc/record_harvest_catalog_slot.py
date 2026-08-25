"""Record one probed or empty catalog slot into accumulated harvest facts."""


def record(selected: dict, probed: dict) -> dict:
    out = dict(selected)
    catalog = dict(out.get("closed_catalog") or {})
    repo = str(selected.get("harvest_repo") or "")
    if selected.get("harvest_route") == "probe":
        catalog[repo] = list(probed.get("closed") or [])
    out["closed_catalog"] = catalog
    return out

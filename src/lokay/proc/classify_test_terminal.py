"""Purely select one closed local-test terminal kind."""


def classify(
    inspected: dict, cached: dict, full: dict, scoped: dict, written: dict
) -> dict:
    if inspected.get("route") == "terminal":
        kind = "inspection"
    elif cached.get("route") == "hit":
        kind = "cached"
    elif written.get("written"):
        kind = "green"
    else:
        kind = "red"
    return {"ok": True, "kind": kind}

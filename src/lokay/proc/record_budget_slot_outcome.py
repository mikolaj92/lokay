"""Stabilize optional harvest and reap effects into one receipt outcome."""


def record(
    selected: dict,
    route: dict,
    harvest: dict,
    terminated: dict,
    stamped: dict,
    parked: dict,
) -> dict:
    if selected.get("route") != "receipt":
        return dict(selected)
    source = (
        parked
        if parked.get("ok")
        else stamped if stamped.get("ok") else harvest if harvest.get("ok") else route
    )
    if source.get("route") == "harvested":
        return {**source, "route": "kept", "reason": "harvested"}
    if source.get("route") == "stamped":
        return {**source, "route": "reaped"}
    return dict(source)

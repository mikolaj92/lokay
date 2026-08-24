"""Stabilize performed, planned, or absent protected-residue restore."""


def record(classified: dict, authorized: dict, restored: dict) -> dict:
    if restored.get("ok"):
        return restored
    if authorized.get("route") == "planned":
        return {
            "ok": True,
            "route": "planned",
            "restored_paths": authorized.get("restore_paths") or [],
        }
    return {"ok": True, "route": "none", "restored_paths": []}

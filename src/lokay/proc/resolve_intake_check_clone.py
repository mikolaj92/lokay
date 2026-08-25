"""Resolve one optional configured checkout path without probing its tree."""

from lokay.proc._common import resolve_repo_clone


def resolve(request: dict, *, config: object) -> dict:
    if request.get("route") != "read":
        return {"ok": True, "clone_path": None}
    try:
        path = resolve_repo_clone(config, request["repo"])
    except KeyError:
        path = None
    return {"ok": True, "clone_path": str(path) if path else None}

"""Write one validated localization evidence file, or report the planned effect."""

from pathlib import Path

from lokay.localize import Localization, write_localize_file


def write(request: dict, validated: dict, *, live: bool) -> dict:
    if validated.get("route") != "write":
        return {
            "ok": True,
            "route": "terminal",
            "reason": validated.get("reason") or "empty_paths",
        }
    root = Path(request["worktree"])
    loc = Localization(
        paths=tuple(validated["paths"]),
        source=str(validated.get("source") or "deterministic"),
        seed_paths=tuple(validated.get("seed_paths") or []),
        matched_tokens=tuple(validated.get("matched_tokens") or []),
        notes=tuple(validated.get("notes") or []),
        worktree=str(root),
        issue=int(request.get("issue") or 0),
    )
    path = str(root / request["rel_path"])
    wrote = False
    if live:
        if not root.is_dir():
            return {"ok": True, "route": "terminal", "reason": "missing_worktree"}
        write_localize_file(root, loc, rel_path=request["rel_path"])
        wrote = True
    return {
        "ok": True,
        "route": "success",
        "planned": not live,
        "wrote": wrote,
        "localize_path": path,
        "localize_rel": request["rel_path"],
        "paths": list(loc.paths),
        "seed_paths": list(loc.seed_paths),
        "matched_tokens": list(loc.matched_tokens),
        "source": loc.source,
        "notes": list(loc.notes),
        "repo": request.get("repo"),
        "issue": request.get("issue"),
    }

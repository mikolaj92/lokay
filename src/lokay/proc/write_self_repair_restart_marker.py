"""Write exactly one validated restart-required marker."""

from pathlib import Path


def write(prepared: dict, outcome: dict) -> dict:
    path = outcome.get("path") or {}
    flag = Path(prepared["state_path"]).parent / "restart-required"
    try:
        flag.write_text(str(path.get("commit") or "1"), encoding="utf-8")
    except OSError as exc:
        return {
            "ok": True,
            "route": "terminal",
            "reason": "restart_marker_failed",
            "error": str(exc),
        }
    return {"ok": True, "route": "written", "commit": path.get("commit")}

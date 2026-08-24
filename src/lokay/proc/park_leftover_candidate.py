"""Park one CLOSED ready issue or report the planned effect."""

from lokay.proc.closeout import _park_ready


def park(selected: dict, *, config_path: str | None) -> dict:
    out = _park_ready(
        repo=selected["repo"],
        issue=int(selected["number"]),
        allowed=bool(selected.get("mutations_allowed")),
        config_path=config_path,
    )
    if not out.get("ok"):
        return {
            **selected,
            "ok": False,
            "error": out.get("error") or "leftover park failed",
        }
    removed = bool(out.get("removed"))
    return {
        **selected,
        "ok": True,
        "route": "removed" if removed else "planned",
        "parked": out,
    }

"""Write tick.json and lift the factory_begin receipt. One file, one job."""

from lokay.passkit import io as pass_io


def persist(workspace: dict, begin: dict, host: dict, ledger: dict) -> dict:
    path = workspace["pass_dir"]
    payload = dict(begin.get("begin") or begin)
    planned = list(payload.get("planned") or [])
    tick = {
        "ok": True,
        "health": "hosted",
        "idle": False,
        "progress": 0,
        "live": bool(payload.get("live")),
        "mode": payload.get("mode"),
        "planned": planned,
        "actions": [],
        "remaining": {},
        "lane": "",
        "note": "workspace opened; issues and prs list live",
    }
    pass_io.write_json(pass_io.tick_path(path), tick)
    return {
        "ok": True,
        "pass_dir": path,
        "stuck_path": str(payload.get("stuck_path") or ledger.get("stuck_path") or ""),
        "planned": planned,
        "live": bool(payload.get("live")),
        "mode": payload.get("mode"),
        "offline": bool(host.get("offline")),
        "issue_count": int(ledger.get("issue_count") or 0),
        "idle": False,
    }

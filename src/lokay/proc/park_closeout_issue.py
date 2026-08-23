"""Park readiness and clear stuck state for one physically closed issue."""

from pathlib import Path
from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park
from lokay.stuck import clear_issue, load_stuck, save_stuck


def park(gate: dict, *, config_path: str | None, live: bool) -> dict:
    item = gate["inspected"]
    issue = item.get("issue")
    if issue is None or not live:
        return {"ok": True, "applied": False, "issue": issue}
    argv = (["--config", config_path] if config_path else []) + [
        "--live",
        "--repo",
        item["repo"],
        "--issue",
        str(issue),
    ]
    out = run_proc(unbounded_park.main, argv)
    raw = str((item.get("policy") or {}).get("stuck_path") or "")
    path = Path(raw)
    if raw:
        stuck = load_stuck(path)
        clear_issue(stuck, item["repo"], int(issue))
        save_stuck(path, stuck)
    return {"ok": True, "issue": issue, "parked": out, "applied": bool(out.get("ok"))}

"""Persist one begin payload, working ledger, and a workspace tick."""

from pathlib import Path

from lokay.passkit import io as pass_io
from lokay.proc.build_factory_begin_state import build as build_begin
from lokay.proc.build_factory_working_state import build as build_working
from lokay.proc.factory_begin_receipt import with_stuck
from lokay.proc.seed_prior_catalog import seed
from lokay.stuck import stuck_path_for


def persist(
    workspace: dict,
    config: dict | None = None,
    scope: dict | None = None,
    host: dict | None = None,
    begin: dict | None = None,
    working: dict | None = None,
) -> dict:
    path = workspace["pass_dir"]
    cfg = dict(config or {})
    scoped = dict(scope or {})
    probed = dict(host or {})
    if begin is None and isinstance(cfg, dict) and "begin" in cfg:
        begin = cfg
        working = scoped if working is None else working
        cfg = {}
        scoped = {}
    if begin is None or working is None:
        ledger = {
            "stuck_path": str(stuck_path_for(Path(cfg["state_path"]))),
            "issue_count": 0,
        }
        begin = build_begin(cfg, scoped, ledger, workspace)
        working = build_working(ledger)
    payload = dict(begin["begin"])
    work = dict(working["working"])
    stuck = with_stuck({"stuck_path": payload["stuck_path"]})["stuck"]
    payload["stuck"] = stuck
    work["stuck"] = stuck
    work = seed(working=work, begin=payload, pass_dir=path)
    pass_io.write_json(pass_io.begin_path(path), payload)
    pass_io.write_json(pass_io.working_path(path), work)
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
    issues = stuck.get("issues") or {}
    return {
        "ok": True,
        "pass_dir": path,
        "stuck_path": payload["stuck_path"],
        "planned": planned,
        "live": bool(payload.get("live")),
        "mode": payload.get("mode"),
        "offline": bool(probed.get("offline")),
        "issue_count": len(issues) if isinstance(issues, dict) else 0,
        "idle": False,
    }

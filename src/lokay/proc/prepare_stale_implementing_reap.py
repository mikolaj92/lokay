"""Prepare bounded catalog and TTL facts for stale-stage recovery."""

import argparse, os
from lokay.proc._common import load_cfg
from lokay.passkit.hot import survey_scope
from lokay.passkit.working import load_begin_working
from lokay.proc.stale_implementing_stamp import (
    stale_stamp_path,
    stale_recently_empty,
    IDLE_STALE_TTL_SECONDS,
)


def prepare(*, pass_dir: str | None, config_path: str | None, slot_count: int) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    repos = [x.name for x in cfg.active_repos()]
    scope = None
    if pass_dir:
        begin, _ = load_begin_working(pass_dir)
        scope = sorted(survey_scope(begin))
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "stale implementing catalog exceeds authored slots",
            "repos": len(repos),
            "slot_count": slot_count,
        }
    stamp = stale_stamp_path(cfg)
    ttl = (
        IDLE_STALE_TTL_SECONDS
        if os.environ.get("LOKAY_LEFTOVER_PROBE_GH_OK") == "1"
        else None
    )
    return {
        "ok": True,
        "route": "recent_empty" if stale_recently_empty(stamp, ttl=ttl) else "probe",
        "repos": repos,
        "scope": scope,
        "stamp": str(stamp) if stamp else "",
        "pass_dir": pass_dir or "",
    }

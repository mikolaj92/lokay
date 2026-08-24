"""Prepare bounded repositories, TTL route, and mutation policy for ready hygiene."""

import argparse, os
from lokay.proc._common import load_cfg, mutations_allowed
from lokay.proc.ready_hygiene import (
    IDLE_HYGIENE_TTL_SECONDS,
    hygiene_recently_empty,
    hygiene_stamp_path,
)


def prepare(*, config_path: str | None, live: bool, slot_count: int) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    repos = [str(x.name) for x in cfg.active_repos()]
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "ready hygiene catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": slot_count,
        }
    ttl = (
        IDLE_HYGIENE_TTL_SECONDS
        if os.environ.get("LOKAY_LEFTOVER_PROBE_GH_OK") == "1"
        else None
    )
    recent = hygiene_recently_empty(hygiene_stamp_path(cfg), ttl=ttl)
    return {
        "ok": True,
        "repos": repos,
        "route": "skip" if recent else "probe",
        "ready_label": str(cfg.ready_label),
        "mutations_allowed": (
            mutations_allowed(live_flag=live, cfg=cfg) if not recent else False
        ),
        "live": live,
    }

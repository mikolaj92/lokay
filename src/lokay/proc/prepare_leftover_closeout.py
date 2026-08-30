"""Prepare bounded catalog, labels, TTL route, and mutation policy for leftover closeout."""

import argparse
from lokay.proc._common import load_cfg, mutations_allowed
from lokay.proc.closeout import (
    leftover_recently_empty,
    leftover_stamp_path,
    WORK_READY_LABEL,
)


def prepare(*, config_path: str | None, live: bool, slot_count: int) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    repos = [str(x.name) for x in cfg.active_repos()]
    recent = leftover_recently_empty(leftover_stamp_path(cfg))
    labels = [WORK_READY_LABEL]
    ready = str(cfg.ready_label or "")
    if ready and ready not in labels:
        labels.append(ready)
    return {
        "ok": True,
        "route": "skip" if recent else "probe",
        "repos": repos,
        "labels": labels,
        "live": live,
        "slot_count": slot_count,
        "mutations_allowed": (
            mutations_allowed(live_flag=live, cfg=cfg) if not recent else False
        ),
    }

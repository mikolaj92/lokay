"""Validate one bounded serial product-pass budget."""

import argparse
from lokay.proc._common import load_cfg


def prepare(
    *, config_path: str | None, live: bool, max_passes: int, slot_count: int
) -> dict:
    budget = max(1, int(max_passes))
    if budget > slot_count:
        return {
            "ok": False,
            "error": "product pass budget exceeds authored slots",
            "budget": budget,
            "slot_count": slot_count,
        }
    cfg = load_cfg(argparse.Namespace(config=config_path))
    if live and cfg.mode != "live":
        return {"ok": False, "error": "refusing --live while config mode is not live"}
    return {
        "ok": True,
        "route": "run",
        "budget": budget,
        "mode": cfg.mode,
        "live": live,
    }

"""Apply the leftover-closeout empty-probe TTL effect."""

import argparse
from lokay.proc._common import load_cfg
from lokay.proc.closeout import (
    leftover_stamp_path,
    _clear_leftover_stamp,
    _touch_leftover_stamp,
)


def update(reduced: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = leftover_stamp_path(cfg)
    if reduced.get("applied") and reduced.get("closed_out"):
        _clear_leftover_stamp(stamp)
    elif (
        not reduced.get("skipped")
        and not reduced.get("probe_failed")
        and not reduced.get("closed_out")
        and getattr(cfg, "mode", "") == "live"
    ):
        _touch_leftover_stamp(stamp)
    return {"ok": True, "result": reduced}

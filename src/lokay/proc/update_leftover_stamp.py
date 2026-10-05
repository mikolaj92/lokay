"""Apply the leftover-closeout empty-probe TTL effect."""

import argparse

from lokay.operator_stamps import clear_stamp, touch_stamp
from lokay.proc._common import load_cfg
from lokay.proc.closeout import leftover_stamp_path


def update(reduced: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = leftover_stamp_path(cfg)
    if reduced.get("applied") and reduced.get("closed_out"):
        clear_stamp(stamp)
    elif (
        not reduced.get("skipped")
        and not reduced.get("probe_failed")
        and not reduced.get("closed_out")
        and getattr(cfg, "mode", "") == "live"
    ):
        touch_stamp(stamp)
    return {"ok": True, "result": reduced}

"""Apply ready-hygiene empty-probe TTL effect."""

import argparse

from lokay.operator_stamps import clear_stamp, touch_stamp
from lokay.proc._common import load_cfg
from lokay.proc.ready_hygiene import hygiene_stamp_path


def update(reduced: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = hygiene_stamp_path(cfg)
    if reduced.get("applied") and reduced.get("cleaned"):
        clear_stamp(stamp)
    elif (
        not reduced.get("skipped")
        and not reduced.get("probe_failed")
        and not reduced.get("cleaned")
        and getattr(cfg, "mode", "") == "live"
    ):
        touch_stamp(stamp)
    return {"ok": True, "result": reduced}

"""Apply ready-hygiene empty-probe TTL effect."""

import argparse
from lokay.proc._common import load_cfg
from lokay.proc.ready_hygiene import (
    _clear_hygiene_stamp,
    _touch_hygiene_stamp,
    hygiene_stamp_path,
)


def update(reduced: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = hygiene_stamp_path(cfg)
    if reduced.get("applied") and reduced.get("cleaned"):
        _clear_hygiene_stamp(stamp)
    elif (
        not reduced.get("skipped")
        and not reduced.get("probe_failed")
        and not reduced.get("cleaned")
        and getattr(cfg, "mode", "") == "live"
    ):
        _touch_hygiene_stamp(stamp)
    return {"ok": True, "result": reduced}

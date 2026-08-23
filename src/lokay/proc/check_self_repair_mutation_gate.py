"""Read whether live mutations are currently permitted for self-repair."""

import argparse
from lokay.proc._common import load_cfg, mutations_allowed


def check(checkout: dict, *, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    return {**checkout, "route": "live" if allowed else "planned", "live": allowed}

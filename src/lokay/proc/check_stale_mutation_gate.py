"""Read the physical mutation capability for stale-stage recovery."""

import argparse
from lokay.proc._common import load_cfg, mutations_allowed


def check(probe: dict, *, config_path: str | None, live: bool) -> dict:
    if not probe.get("candidates"):
        return {"ok": True, "route": "no_candidates", "apply": False}
    cfg = load_cfg(argparse.Namespace(config=config_path))
    apply = mutations_allowed(live_flag=live, cfg=cfg)
    return {"ok": True, "route": "apply" if apply else "plan", "apply": apply}

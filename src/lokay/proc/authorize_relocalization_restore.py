"""Apply the mutation gate to one protected-residue restore set."""

import argparse

from lokay.proc._common import load_cfg, mutations_allowed


def authorize(classified: dict, *, config_path: str | None, live: bool) -> dict:
    if classified.get("route") != "restore":
        return {"ok": True, "route": "unused", "restore_paths": []}
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    return {
        "ok": True,
        "route": "restore" if allowed else "planned",
        "restore_paths": classified["restore_paths"],
        "live": allowed,
    }

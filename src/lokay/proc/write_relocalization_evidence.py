"""Write one authoritative approved scope expansion, or report planned effect."""

import argparse
import json
from pathlib import Path

from lokay.proc._common import load_cfg, mutations_allowed


def write(
    evidence: dict,
    offgoal: dict,
    approval: dict,
    *,
    config_path: str | None,
    live: bool,
) -> dict:
    merged = list(
        dict.fromkeys([*evidence.get("localized", []), *approval.get("approved", [])])
    )
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    path = Path(evidence["worktree"]) / ".lokay/localize.json"
    if allowed:
        payload = {
            "paths": merged,
            "source": "agent",
            "notes": ["One bounded off-goal relocalization approved required paths."],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return {
        "ok": True,
        "route": "success",
        "planned": not allowed,
        "retried": True,
        "approved_paths": approval.get("approved") or [],
        "paths": merged,
        "restored_paths": offgoal.get("restored_paths") or [],
        "worktree": evidence["worktree"],
    }

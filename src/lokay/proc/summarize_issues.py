"""Receipt for one issues child pass. Empty list and sito skip still write."""

from __future__ import annotations

import json
from pathlib import Path


def summarize(
    picked: dict,
    do: dict,
    launched: dict,
    *,
    pass_dir: str = "",
) -> dict:
    route = str(do.get("route") or picked.get("route") or "none")
    receipt = {
        "ok": True,
        "result": {
            "issue": picked.get("issue"),
            "repo": picked.get("repo"),
            "route": route,
            "reason": do.get("reason") or picked.get("reason"),
            "launched": launched.get("route"),
        },
    }
    if pass_dir:
        path = Path(pass_dir) / "issues-receipt.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt["result"], ensure_ascii=False), encoding="utf-8")
        receipt["result"]["receipt"] = str(path)
    return receipt

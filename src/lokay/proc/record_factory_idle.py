"""Write last-pass receipt for an authored idle factory_pass exit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.pass_history import append_pass_receipt
from lokay.pass_receipt import build_pass_receipt, write_pass_receipt


def record(classified: dict[str, Any], *, config_path: str | None = None) -> dict[str, Any]:
    remaining = classified.get("remaining")
    if not isinstance(remaining, dict):
        remaining = {}
    tick = {
        "ok": True,
        "health": "idle",
        "idle": True,
        "live": bool(classified.get("live")),
        "progress": int(classified.get("progress") or 0),
        "remaining": remaining,
        "lane": "idle",
        "skipped": True,
        "reason": str(classified.get("reason") or "recent_empty_survey"),
        "kind": "factory_pass",
        "engine": "fala",
    }
    receipt = build_pass_receipt(
        tick=tick,
        merge_enabled=False,
        require_checks=False,
        require_llm_review=True,
        max_issue_to_pr_per_pass=1,
        config_path=config_path,
    )
    try:
        written = write_pass_receipt(receipt)
        append_pass_receipt(receipt, state_path=Path.home() / ".lokay" / "state.jsonl")
        tick["pass_receipt_path"] = str(written)
    except OSError as exc:
        tick["pass_receipt_error"] = str(exc)
    return {"ok": True, "result": tick, **tick}

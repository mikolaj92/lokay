"""Prepare bounded receipt inputs and the stuck-ledger location."""

import json
from pathlib import Path
from lokay.proc.detach_issue_to_pr import live_issue_to_pr_receipts


def prepare(*, pass_dir: str | None, budget_s: int, slot_count: int) -> dict:
    rows = live_issue_to_pr_receipts()
    if len(rows) > slot_count:
        return {
            "ok": False,
            "error": "over-budget receipts exceed authored slots",
            "receipts": len(rows),
            "slot_count": slot_count,
        }
    configured = ""
    if pass_dir:
        try:
            data = json.loads((Path(pass_dir) / "begin.json").read_text())
            configured = (
                str(data.get("stuck_path") or "") if isinstance(data, dict) else ""
            )
        except (OSError, ValueError):
            pass
    return {
        "ok": True,
        "receipts": rows,
        "budget_s": budget_s,
        "stuck_path": configured or str(Path.home() / ".lokay" / "stuck.json"),
        "pass_dir": pass_dir or "",
    }

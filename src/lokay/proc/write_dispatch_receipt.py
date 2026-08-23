"""Publish one running pass receipt after successful dispatch."""

from pathlib import Path
from lokay.pass_receipt import build_pass_receipt, write_pass_receipt
from lokay.passkit import io as pass_io


def write(*, pass_dir: str) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    started = int(working.get("issue_to_pr_started") or 0)
    receipt = build_pass_receipt(
        tick={
            "ok": True,
            "health": "running",
            "progress": int(working.get("progress") or 0),
            "live": True,
            "remaining": {
                "issue_to_pr_started": started,
                "max_issue_to_pr_per_pass": int(
                    begin.get("max_issue_to_pr_per_pass") or 0
                ),
                "ready": int(working.get("remaining_ready") or 0),
                "actionable_open_ai_prs": int(working.get("actionable_prs") or 0),
            },
            "note": "implement detached; last-pass does not wait on worker",
        },
        merge_enabled=bool(begin.get("merge_enabled")),
        require_checks=bool(begin.get("require_checks")),
        require_llm_review=bool(begin.get("require_llm_review")),
        max_issue_to_pr_per_pass=int(begin.get("max_issue_to_pr_per_pass") or 0),
        config_path=begin.get("config_path"),
    )
    try:
        write_pass_receipt(
            receipt,
            state_path=Path(
                str(begin.get("state_path") or Path.home() / ".lokay" / "state.jsonl")
            ),
        )
    except OSError:
        return {"ok": True, "applied": False, "reason": "receipt_write_failed"}
    return {"ok": True, "applied": True, "started": started}

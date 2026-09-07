"""Persist one bounded implementation launch failure and select its Fala route."""

from datetime import datetime, timedelta, timezone

from lokay.passkit import io as pass_io
from lokay.stuck import (
    TRANSIENT_COOLDOWN_SECONDS,
    is_transient_ledger_reason,
    record_failure,
)


def apply(*, pass_dir: str, launched: dict) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    repo = str(launched["repo"])
    issue = int(launched["issue"])
    result = dict(launched.get("launch") or {})
    stuck = dict(working.get("stuck") or {})
    reason = str(result.get("reason") or "") or "dispatch_failure"
    row = record_failure(
        stuck,
        repo=repo,
        number=issue,
        error=str(result.get("error") or result.get("fala") or "issue_to_pr failed"),
        max_failures=int(begin.get("max_fail") or 1),
        reason=reason,
        cooldown_seconds=TRANSIENT_COOLDOWN_SECONDS,
    )
    # Verify / local-repair must never eternal-block, but do start a cooldown
    # immediately so the same ticket cannot monopolize the single product slot.
    if is_transient_ledger_reason(reason) or reason == "local_repair_exhausted":
        if not row.get("blocked"):
            now = datetime.now(timezone.utc)
            row["blocked"] = True
            row["blocked_ts"] = now.isoformat()
            row["cooldown_seconds"] = TRANSIENT_COOLDOWN_SECONDS
            row["cooldown_until"] = (
                now + timedelta(seconds=TRANSIENT_COOLDOWN_SECONDS)
            ).isoformat()
            stuck.setdefault("issues", {})[f"{repo}#{issue}"] = row
    working["stuck"] = stuck
    working["actions"] = [
        *list(working.get("actions") or []),
        {
            "step": "record_stuck",
            "repo": repo,
            "issue": issue,
            "failures": row.get("failures"),
            "blocked": bool(row.get("blocked")),
            "cooldown_until": row.get("cooldown_until"),
        },
    ]
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {
        "ok": True,
        "route": "blocked" if row.get("blocked") else "retry_later",
        "plan_only": str(result.get("error") or result.get("reason") or "")
        == "plan_only",
        "repo": repo,
        "issue": issue,
        "failure": result,
    }

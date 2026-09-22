"""Pick one open lokay PR. Skip without merge walks leftover like issues."""

from lokay.proc.walk_pr_leftover import queue, skipped_fields


def select(listed: dict, last: dict | None = None) -> dict:
    if listed.get("ok") is False:
        return {
            "ok": False,
            "route": "none",
            "reason": "list_failed",
            "error": listed.get("error"),
        }
    rows = [row for row in list(listed.get("prs") or []) if isinstance(row, dict)]
    remembered = dict(last or {})
    if any(row.get('delivery_replay') and row.get('repo') == (remembered.get('skipped_pr_repo') or remembered.get('skipped_repo'))
           and row.get('pr') == remembered.get('skipped_pr') for row in rows):
        remembered.pop('skipped_pr', None)
    queued = [
        row
        for row in queue(rows, remembered)
        if row.get("repo") and row.get("pr") and row.get("branch")
    ]
    if not queued:
        out = {"ok": True, "route": "none", "reason": "no_open_pr"}
        if isinstance(last, dict) and (
            last.get("skipped_pr") is not None or "leftover_prs" in last
        ):
            out["leftover"] = 0
            out["leftover_prs"] = []
            out.update(skipped_fields(last))
        return out
    row = dict(queued[0])
    rest = [dict(item) for item in queued[1:]]
    return {
        **row,
        "ok": True,
        "route": "pr",
        "leftover": len(rest),
        "leftover_prs": rest,
    }

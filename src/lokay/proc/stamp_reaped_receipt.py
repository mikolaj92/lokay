"""Stamp one terminated receipt without hiding it from harvest."""

import json
from lokay.proc.detach_issue_to_pr import issue_to_pr_receipt_path


def stamp(terminated: dict) -> dict:
    row = dict(terminated.get("receipt") or {})
    row.update(ok=False, reason=terminated.get("reason"), reaped=True)
    written = False
    try:
        issue_to_pr_receipt_path(
            terminated["repo"], int(terminated["issue"])
        ).write_text(json.dumps(row))
        written = True
    except OSError:
        pass
    return {**terminated, "route": "stamped", "receipt_stamped": written}

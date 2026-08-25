"""Read local detached-child receipts and issue-to-PR journal facts once."""

import json
from pathlib import Path

from lokay.child_harvest import _index_issue_to_pr_log, _isolated_mill_roots


def collect(config: dict, scope: dict, ledger: dict) -> dict:
    state = Path(config["state_path"])
    home = Path.home()
    default_cycle, isolated = _isolated_mill_roots(state, home)
    home = isolated
    receipts = []
    if default_cycle.is_dir():
        for path in sorted(default_cycle.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                receipts.append(data)
    events, history = _index_issue_to_pr_log(state)
    return {
        "ok": True,
        "state_path": str(state),
        "cycle_dir": str(default_cycle),
        "home": str(home),
        "repos": list(scope.get("repos") or []),
        "stuck_path": str(ledger["stuck_path"]),
        "stuck": dict(ledger.get("stuck") or {}),
        "receipts": receipts,
        "events": {f"{r}#{i}": v for (r, i), v in events.items()},
        "history": {f"{r}#{i}": v for (r, i), v in history.items()},
    }

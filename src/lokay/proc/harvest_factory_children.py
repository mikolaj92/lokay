"""Apply one fail-closed harvest to the loaded detached-child receipts."""

from pathlib import Path
from lokay.child_harvest import harvest_fail_closed_children


def harvest(config: dict, scope: dict, ledger: dict) -> dict:
    stuck = dict(ledger.get("stuck") or {})
    harvest_fail_closed_children(
        stuck,
        state_path=Path(config["state_path"]),
        repos=list(scope.get("repos") or []),
    )
    return {"ok": True, "stuck": stuck}

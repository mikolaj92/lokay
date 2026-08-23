"""Clear one issue from the durable stuck ledger."""

from lokay.passkit.working import load_begin_working, stuck_path_of
from lokay.stuck import clear_issue, save_stuck


def clear(*, pass_dir: str, resolved: dict) -> dict:
    begin, working = load_begin_working(pass_dir)
    stuck = dict(working.get("stuck") or begin.get("stuck") or {})
    clear_issue(stuck, str(resolved["repo"]), int(resolved["issue"]))
    save_stuck(stuck_path_of(begin), stuck)
    return {"ok": True, "stuck": stuck, **resolved}

"""Prepare bounded catalog and closeout policy from one pass workspace."""

from lokay.passkit.working import load_begin_working
from lokay.proc.pass_lane import product_candidates, self_repo


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin, working = load_begin_working(pass_dir)
    repos = list(begin.get("repos") or [])
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "PR closeout catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": slot_count,
        }
    self_id = self_repo(begin)
    ready = dict(working.get("ready_by_repo") or {})
    prs = dict(working.get("prs_by_repo") or {})
    return {
        "ok": True,
        "repos": repos,
        "prs_by_repo": prs,
        "ready_by_repo": ready,
        "self_repo": self_id,
        "product_queue": product_candidates(
            ready_by_repo=ready, prs_by_repo=prs, self_id=self_id
        ),
        "repair_budget": int(begin.get("repair_budget") or 0),
        "policy": {
            "merge_enabled": bool(begin.get("merge_enabled")),
            "require_checks": bool(begin.get("require_checks")),
            "executor_enabled": bool(begin.get("executor_enabled")),
            "branch_prefix": str(begin.get("branch_prefix") or "ai/fix/"),
            "stuck_path": str(begin.get("stuck_path") or ""),
        },
    }

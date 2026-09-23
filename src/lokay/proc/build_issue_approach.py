"""Build and render one deterministic issue approach."""

from pathlib import Path

from lokay.approach_plan import build_approach, render_approach_md
from lokay.models import Issue


def build(request: dict) -> dict:
    worktree = Path(request["worktree"])
    plan = build_approach(
        Issue.from_dict(request["issue"]),
        worktree=worktree if worktree.is_dir() else None,
    )
    from lokay.proc.validate_plan import validate_plan

    verdict = validate_plan(plan.to_dict())
    if not verdict["ok"]:
        return {"ok": False, "reason": verdict["reason"], "plan": plan.to_dict()}
    return {
        "ok": True,
        "plan": plan.to_dict(),
        "source": plan.source,
        "content": render_approach_md(plan),
        "approach_path": str(worktree / request["rel_path"]),
    }

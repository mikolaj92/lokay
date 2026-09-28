import argparse
import json
from pathlib import Path

from lokay.approach_plan import build_approach, render_approach_md
from lokay.models import Issue
from lokay.pr_review import PrReviewError, extract_json_object

_PROMPT = """Read the issue and the repository. Reply with one JSON object and nothing else:
{{"ok": true, "goal": "...", "files": ["relative/path.py"], "test_plan": ["..."],
"non_goals": ["..."], "test_command": "..."}}
files are paths you will change. Name none when you cannot tell.
Or, when the issue should not be implemented: {{"ok": false, "reason": "underspecified"|"too_large"|"dangerous"}}

Issue #{number} — {title}

{body}
"""


def build(request: dict, *, execute=None) -> dict:
    worktree = Path(request["worktree"])
    issue = Issue.from_dict(request["issue"])
    tree = worktree if worktree.is_dir() else None
    verdict = _agent_verdict(request, issue, tree, execute)
    if verdict.get("failed"):
        return {"ok": False, "reason": verdict["reason"], "plan": {}}
    agent = verdict.get("agent")
    plan = build_approach(issue, worktree=tree, agent=agent)
    from lokay.proc.validate_plan import validate_plan

    checked = validate_plan(json.dumps(agent))
    if not checked["ok"]:
        return {"ok": False, "reason": checked["reason"], "plan": plan.to_dict()}
    return {
        "ok": True,
        "plan": plan.to_dict(),
        "source": plan.source,
        "content": render_approach_md(plan),
        "approach_path": str(worktree / request["rel_path"]),
    }


def _agent_verdict(request: dict, issue: Issue, worktree: Path | None, execute) -> dict:
    prompt = _PROMPT.format(number=issue.number, title=issue.title or "", body=issue.body or "")
    if execute is not None:
        result = execute(prompt)
    else:
        result = _run(request, issue, worktree, prompt)
    if result.get("status") != "completed":
        return {"failed": True, "reason": str(result.get("status") or "executor_failed")}
    try:
        data = extract_json_object(str(result.get("result_stdout") or result.get("stdout_tail") or ""))
    except PrReviewError:
        return {"failed": True, "reason": "plan_not_json"}
    return {"agent": data}


def _run(request: dict, issue: Issue, worktree: Path | None, prompt: str) -> dict:
    from lokay.proc._issue_triage_agent_runtime import execute

    cfg = _config(request)
    if cfg is None:
        return {"status": "no_config"}
    return execute(
        cfg=cfg,
        repo=issue.repo,
        issue=int(issue.number),
        clone_path=str(worktree) if worktree else "",
        prompt=prompt,
        live=bool(request.get("live")),
    )


def _config(request: dict):
    from lokay.proc._common import load_cfg

    path = str(request.get("config_path") or "") or None
    try:
        return load_cfg(argparse.Namespace(config=path))
    except Exception:
        return None

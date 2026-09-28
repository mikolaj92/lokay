import argparse

from lokay.models import Issue
from lokay.pr_review import PrReviewError, extract_json_object


def ask(issue: Issue, raw: dict, prompt: str, execute) -> dict | None:
    if execute is not None:
        result = execute(prompt)
    else:
        result = _run(issue, raw, prompt)
    if not isinstance(result, dict) or result.get("status") != "completed":
        return None
    text = result.get("result_stdout") or result.get("stdout_tail") or ""
    try:
        data = extract_json_object(str(text))
    except PrReviewError:
        return None
    return data if isinstance(data, dict) else None


def _run(issue: Issue, raw: dict, prompt: str) -> dict:
    from pathlib import Path
    from lokay.agent import run_agent
    from lokay.proc._common import load_cfg, runner, semantic_agent_allowed

    worktree = Path(str(raw.get("clone_path") or raw.get("worktree") or ""))
    try:
        cfg = load_cfg(argparse.Namespace(config=raw.get("config_path") or None))
    except Exception:
        return {"status": "no_config"}
    if not worktree.is_dir() or not semantic_agent_allowed(cfg, live_flag=bool(raw.get("live"))):
        return {"status": "disabled"}
    return run_agent(
        runner(cfg), cfg, worktree=worktree, prompt=prompt, execute=True,
        session_kind="plan", timeout_seconds=110, attach_collector_boundary=False,
        repo=issue.repo, issue=int(issue.number),
    )

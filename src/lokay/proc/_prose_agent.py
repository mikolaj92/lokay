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
    try:
        data = extract_json_object(str(result.get("result_stdout") or ""))
    except PrReviewError:
        return None
    return data if isinstance(data, dict) else None


def _run(issue: Issue, raw: dict, prompt: str) -> dict:
    from lokay.proc._common import load_cfg
    from lokay.proc._issue_triage_agent_runtime import execute

    try:
        cfg = load_cfg(argparse.Namespace(config=raw.get("config_path") or None))
    except Exception:
        return {"status": "no_config"}
    return execute(
        cfg=cfg, repo=issue.repo, issue=int(issue.number),
        clone_path=str(raw.get("clone_path") or ""), prompt=prompt,
        live=bool(raw.get("live")),
    )

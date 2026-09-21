"""Run the authored PR-repair sub-Fala once."""

import json

from lokay.compose.pr_repair import compose_pr_repair


def _coding_attempt(step: dict, *, reason: str) -> bool:
    if step.get("step") != "run_agent":
        return False
    # Failed organs carry their envelope as JSON error, not output payload.
    error = step.get("error") or {}
    try:
        if isinstance(error, str):
            error = json.loads(error)
        if isinstance(error, dict) and "message" in error:
            error = json.loads(str(error["message"]).rsplit("RuntimeError: ", 1)[-1])
    except (TypeError, ValueError):
        error = {}
    return (
        type(step.get("returncode")) is int
        or (isinstance(error, dict) and type(error.get("returncode")) is int)
        or (step.get("status") == "failed" and reason == "agent_failed")
    )


def repair(
    gate: dict, authorized: dict, *, config_path: str | None, live: bool = True
) -> dict:
    if not live or authorized.get("route") != "repair":
        return {"ok": True, "repair_used": 0, "skipped": True}
    item = gate["inspected"]
    kw = {
        "config_path": config_path,
        "repo": item["repo"],
        "pr_number": item["pr_number"],
        "branch": item["head"],
        "live": live,
        **{key: authorized[key] for key in (
            "repair_kind", "repair_start_head_sha", "reviewed_head_sha",
            "task", "findings", "task_identity_sha256", "review_result_sha256",
        )},
    }
    review = authorized.get("review") or None
    if review is not None:
        kw["review"] = review
    try:
        out = compose_pr_repair(**kw)
    except Exception:  # noqa: BLE001 — child infrastructure failure is not an attempt.
        out = {"ok": False, "error": "compose_error"}
    nested = out.get("result")
    result = nested if isinstance(nested, dict) else out
    # CLI budget counts an actual coding invocation or published correction.
    # Unlike the daemon's lifetime receipt, this does not require a push to count.
    attempted = any(
        _coding_attempt(step, reason=str(out.get("reason") or ""))
        for step in out.get("steps", [])
    )
    published = result.get("repaired") is True and result.get("published") is True
    return {
        "ok": True,
        "repair": out,
        "repair_used": int(attempted or published),
        "step": authorized.get("step") or "pr_repair",
    }

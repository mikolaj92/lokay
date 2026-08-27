"""Invoke the authored coding-execution Fala."""

from lokay.graph_run import run_path


def failed(error: object = None, reason: str = "coding_execution_failed") -> dict:
    """Classified child failure the parent when can read. Never process.failed."""
    if isinstance(error, BaseException):
        message = str(error).strip() or type(error).__name__
    elif error not in (None, "", {}):
        message = str(error)
    else:
        message = "empty coding_execution child"
    payload = {
        "ok": True,
        "route": "failed",
        "decision": {},
        "evidence_kind": "none",
        "reason": reason,
        "error": message,
    }
    return {**payload, "result": dict(payload)}


def run(
    *,
    config_path: str | None,
    live: bool,
    extra_inputs: dict,
) -> dict:
    try:
        out = run_path(
            path_id="coding_execution",
            repo=str(extra_inputs.get("repo") or "local/coding"),
            issue=extra_inputs.get("issue"),
            config_path=config_path,
            live=live,
            max_ticks=64,
            extra_inputs=extra_inputs,
        )
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return failed(exc)
    if not out.get("ok"):
        return failed(out.get("error") or out.get("reason") or out)
    route = str(out.get("route") or "")
    if not route:
        return failed(out.get("error") or "empty coding_execution child")
    return {
        "ok": True,
        "route": route,
        "decision": dict(out.get("decision") or {}),
        "evidence_kind": str(out.get("evidence_kind") or "none"),
        "reason": out.get("reason"),
    }

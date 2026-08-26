"""Invoke the authored local-repair execution Fala."""

from lokay.graph_run import run_path


def run(
    *,
    config_path: str | None,
    live: bool,
    extra_inputs: dict,
) -> dict:
    out = run_path(
        path_id="local_repair_execution",
        repo=str(extra_inputs.get("repo") or "local/repair"),
        issue=extra_inputs.get("issue"),
        config_path=config_path,
        live=live,
        max_ticks=32,
        extra_inputs=extra_inputs,
    )
    if not out.get("ok"):
        return out
    return {
        "ok": True,
        "route": out.get("route") or "terminal",
        "reason": out.get("reason"),
        "decision": dict(out.get("decision") or {}),
        "passed": bool(out.get("passed")),
    }

"""Invoke the authored coding-execution Fala."""

from lokay.graph_run import run_path


def run(
    *,
    config_path: str | None,
    live: bool,
    extra_inputs: dict,
) -> dict:
    out = run_path(
        path_id="coding_execution",
        repo=str(extra_inputs.get("repo") or "local/coding"),
        issue=extra_inputs.get("issue"),
        config_path=config_path,
        live=live,
        max_ticks=64,
        extra_inputs=extra_inputs,
    )
    if not out.get("ok"):
        return out
    return {
        "ok": True,
        "route": out.get("route") or "human",
        "decision": dict(out.get("decision") or {}),
        "evidence_kind": str(out.get("evidence_kind") or "none"),
        "reason": out.get("reason"),
    }

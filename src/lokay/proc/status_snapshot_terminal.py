"""Close one read-only status snapshot without mutating product state."""


def terminal(reduced: dict) -> dict:
    out = dict(reduced.get("snapshot") or {})
    ready = bool(out.get("mill_ready"))
    out["ok"] = ready
    out["note"] = "read-only durable snapshot; product and GitHub survey not run"
    out["live_env_hint"] = (
        None
        if ready
        else "LOKAY_MODE=live LOKAY_EXECUTOR_ENABLED=1 LOKAY_MERGE_ENABLED=1 uv run lokay-mill --config config.yaml --live"
    )
    if not ready:
        out["error"] = "not working: Lokay is not live-ready"
    return {"ok": True, "result": out}

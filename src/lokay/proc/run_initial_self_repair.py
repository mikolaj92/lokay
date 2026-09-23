"""Run exactly one authored emergency self-repair subflow from preflight evidence."""

from lokay.self_repair import run_self_repair


def run(preflight: dict, *, config_path: str, live: bool = True) -> dict:
    if not live:
        return {"ok": True, "route": "skipped", "reason": "dry_run"}
    result = run_self_repair(config_path, preflight)
    return {
        "ok": True,
        "route": "restart" if result.get("ok") else "failed",
        "repair": result,
    }

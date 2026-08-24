"""Run one factory carrier preflight when no capability was delegated."""

from lokay.preflight import run_preflight


def run(*, config_path: str | None, live: bool) -> dict:
    result = run_preflight(config_path, remediate=True) if live else {"ok": True}
    return {
        "ok": True,
        "route": "load" if result.get("ok") else "terminal",
        "preflight": result,
    }

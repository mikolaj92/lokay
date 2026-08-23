"""Read GitHub checks for one qualified PR."""

from lokay.passkit.support import run_proc
from lokay.proc import pr_checks


def read(gate: dict, *, config_path: str | None) -> dict:
    item = gate["inspected"]
    argv = (["--config", config_path] if config_path else []) + [
        "--repo",
        item["repo"],
        "--pr",
        str(item["pr_number"]),
    ]
    out = run_proc(pr_checks.main, argv)
    return {
        "ok": True,
        "route": "route" if out.get("ok") else "checks_error",
        "checks": out,
    }

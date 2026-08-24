"""Run one explicitly requested read-only host preflight inspection."""

from lokay.preflight import run_preflight


def run(config: dict) -> dict:
    return {
        "ok": True,
        "route": "record",
        "preflight": run_preflight(
            config["config"], remediate=False, issue_lease=False
        ),
    }

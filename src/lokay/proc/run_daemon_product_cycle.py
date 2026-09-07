"""Run exactly one authored bounded daemon product/recovery cycle."""

from lokay.compose.daemon_cycle import compose_daemon_cycle, resolve_pass_ceiling_seconds


def run(
    *,
    config_path: str,
    max_passes: int,
    pass_ceiling_seconds: float | None = None,
) -> dict:
    ceiling = resolve_pass_ceiling_seconds(pass_ceiling_seconds)
    return {
        "ok": True,
        "route": "terminal",
        "payload": compose_daemon_cycle(
            config_path=config_path,
            max_passes=max_passes,
            pass_ceiling_seconds=ceiling,
        ),
    }

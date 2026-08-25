"""Run exactly one authored bounded daemon product/recovery cycle."""

from lokay.compose.daemon_cycle import compose_daemon_cycle


def run(*, config_path: str, max_passes: int) -> dict:
    return {
        "ok": True,
        "route": "terminal",
        "payload": compose_daemon_cycle(config_path=config_path, max_passes=max_passes),
    }

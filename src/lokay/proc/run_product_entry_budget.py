"""Run exactly one hosted factory_pass. Leftover is a child of step (3), not a mill sibling."""

from lokay.compose.factory import compose_factory_pass


def execute(*, config_path: str | None, live: bool, max_passes: int) -> dict:
    del max_passes
    return {
        "ok": True,
        "route": "terminal",
        "payload": compose_factory_pass(config_path=config_path, live=live),
    }

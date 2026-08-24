"""Run one authored parent factory-pass sub-Fala."""

from pathlib import Path
from lokay.compose.factory import compose_factory_pass


def run(*, config_path: str | None, live: bool, slot: int) -> dict:
    return compose_factory_pass(
        config_path=config_path,
        live=live,
        db_path=Path.home() / ".lokay" / "fala" / f"factory-slot-{slot}",
    )

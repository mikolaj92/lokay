"""Read the current health lease without acquiring or mutating it."""

from pathlib import Path

from lokay.preflight import health_lease_status


def read(config: dict) -> dict:
    ok, reason = health_lease_status(
        lock_path=Path(config["state_path"]).parent / "mill.lock"
    )
    return {"ok": True, "lease_ok": ok, "lease_reason": reason}

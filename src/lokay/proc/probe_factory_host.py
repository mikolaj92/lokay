"""Short host-alive fact. Never fail-closes the pass into idle or skip."""

import os


def probe() -> dict:
    offline = os.environ.get("LOKAY_OFFLINE", "").strip().lower() in {"1", "true", "yes"}
    return {
        "ok": True,
        "route": "up",
        "host": "offline" if offline else "up",
        "offline": offline,
    }

"""Terminate one worker whose issue is authoritatively closed."""

import os, signal


def terminate(inspected: dict) -> dict:
    try:
        pid = int(inspected["receipt"]["pid"])
        os.kill(pid, signal.SIGTERM)
        terminated = True
    except ProcessLookupError:
        terminated = True
    except (KeyError, TypeError, ValueError, OSError):
        terminated = False
    return {
        "ok": True,
        "route": "terminated" if terminated else "keep",
        "terminated": terminated,
        **inspected,
    }

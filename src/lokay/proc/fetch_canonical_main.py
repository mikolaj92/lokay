"""Fetch exactly origin/main in one canonical checkout."""

import subprocess


def fetch(prepared: dict) -> dict:
    done = subprocess.run(
        ["git", "-C", prepared["path"], "fetch", "origin", "main"],
        stdin=subprocess.DEVNULL,
        timeout=300,
        check=False,
    )
    return {
        "ok": True,
        "route": "fetched" if done.returncode == 0 else "terminal",
        "reason": "" if done.returncode == 0 else "fetch_failed",
    }

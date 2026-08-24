"""Read porcelain status of one canonical checkout."""

import subprocess


def read(prepared: dict) -> dict:
    done = subprocess.run(
        ["git", "-C", prepared["path"], "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "ok": True,
        "route": "classify" if done.returncode == 0 else "terminal",
        "reason": "" if done.returncode == 0 else "status_failed",
        "dirty": bool(done.stdout.strip()),
        "returncode": done.returncode,
    }

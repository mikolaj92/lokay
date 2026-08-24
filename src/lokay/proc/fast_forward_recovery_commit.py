"""Fast-forward one canonical checkout to an exact recovery commit."""

import subprocess


def merge(prepared: dict) -> dict:
    done = subprocess.run(
        ["git", "-C", prepared["path"], "merge", "--ff-only", prepared["commit"]],
        stdin=subprocess.DEVNULL,
        timeout=300,
        check=False,
    )
    return {
        "ok": True,
        "route": "merged" if done.returncode == 0 else "terminal",
        "reason": "" if done.returncode == 0 else "fast_forward_failed",
    }

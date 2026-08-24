"""Read HEAD after one recovery fast-forward attempt."""

import subprocess


def read(prepared: dict) -> dict:
    done = subprocess.run(
        ["git", "-C", prepared["path"], "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    sha = (done.stdout or "").strip()
    return {
        "ok": True,
        "route": "classify" if done.returncode == 0 and sha else "terminal",
        "reason": "" if done.returncode == 0 and sha else "head_unreadable",
        "head": sha,
    }

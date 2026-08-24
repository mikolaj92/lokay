"""Check whether one recovery commit already exists on origin/main."""

import subprocess


def check(prepared: dict) -> dict:
    done = subprocess.run(
        [
            "git",
            "-C",
            prepared["path"],
            "merge-base",
            "--is-ancestor",
            prepared["commit"],
            "origin/main",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "ok": True,
        "route": "published" if done.returncode == 0 else "terminal",
        "reason": "dirty_tree",
        "published": done.returncode == 0,
    }

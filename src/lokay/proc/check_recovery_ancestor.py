"""Check one recovery commit ancestry against one named Git tip."""

import subprocess


def check(prepared: dict, *, tip: str) -> dict:
    done = subprocess.run(
        [
            "git",
            "-C",
            prepared["path"],
            "merge-base",
            "--is-ancestor",
            prepared["commit"],
            tip,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "ok": True,
        "route": "ancestor" if done.returncode == 0 else "not_ancestor",
        "tip": tip,
    }

"""Fetch the canonical origin/main reference."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def fetch(verified: dict) -> dict:
    runner().run_checked(
        git_spec(
            ["fetch", "origin", "main"],
            cwd=Path(verified["clone"]),
            timeout_seconds=300,
        ),
        live=True,
    )
    return {**verified, "ok": True, "route": "fetched"}

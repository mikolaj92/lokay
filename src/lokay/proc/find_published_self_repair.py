"""Find an origin/main commit carrying the exact recovery fingerprint."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def find(fetched: dict, run=None) -> dict:
    out = (run or runner()).run(
        git_spec(
            [
                "log",
                "origin/main",
                "--grep",
                f"self-repair: {fetched['fingerprint']}",
                "-1",
                "--format=%H",
            ],
            cwd=Path(fetched["clone"]),
            timeout_seconds=60,
        ),
        live=True,
    )
    rows = (out.stdout or "").strip().splitlines()
    commit = rows[0] if rows and len(rows[0]) >= 7 else ""
    return {
        **fetched,
        "route": "published" if commit else "unpublished",
        "commit": commit,
    }

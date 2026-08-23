"""Read the fetched origin/main base SHA."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def read(published: dict) -> dict:
    out = runner().run_checked(
        git_spec(["rev-parse", "origin/main"], cwd=Path(published["clone"])), live=True
    )
    return {
        **published,
        "ok": True,
        "route": "inspect" if published.get("exists") else "create",
        "base_sha": out.stdout.strip(),
    }

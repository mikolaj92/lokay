"""Verify the canonical physical Git origin."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec

ALLOWED = {"https://github.com/mikolaj92/lokay", "git@github.com:mikolaj92/lokay"}


def verify(gate: dict) -> dict:
    out = runner().run_checked(
        git_spec(["remote", "get-url", "origin"], cwd=Path(gate["clone"])), live=True
    )
    origin = out.stdout.strip().removesuffix(".git")
    return {
        **gate,
        "route": "verified" if origin in ALLOWED else "invalid_origin",
        "origin": origin,
        "ok": origin in ALLOWED,
        "error": "" if origin in ALLOWED else "canonical Lokay origin mismatch",
    }

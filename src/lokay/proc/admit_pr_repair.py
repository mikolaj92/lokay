"""Admit pr_repair only while the target PR is still OPEN.

MERGED (and CLOSED) → route=skip. Probe flake → fail-open (route=open).
"""

from __future__ import annotations

import argparse
from typing import Any, Mapping

from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config_read, read_live
from lokay.proc.probe_pr_state import probe as probe_pr_state


def admit(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Pure classify of a probe_pr_state envelope."""
    route = str(probe.get("route") or "")
    repo = str(probe.get("repo") or "")
    pr = int(probe.get("pr") or 0)
    if route == "merged" or bool(probe.get("merged")):
        return ok(
            route="skip",
            reason="pr_already_merged",
            repo=repo,
            pr=pr,
            state=str(probe.get("state") or "MERGED"),
            merged=True,
        )
    if route == "closed":
        return ok(
            route="skip",
            reason="pr_closed",
            repo=repo,
            pr=pr,
            state="CLOSED",
            merged=False,
        )
    # open + unavailable (flake) → admit; fail-open
    return ok(
        route="open",
        reason=str(probe.get("reason") or "pr_open"),
        repo=repo,
        pr=pr,
        state=str(probe.get("state") or "OPEN"),
        merged=False,
        probe_route=route,
    )


def admit_live(*, repo: str, pr: int, live: bool) -> dict[str, Any]:
    return admit(probe_pr_state(repo=repo, pr=pr, live=live))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-admit-pr-repair")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    args = p.parse_args(argv)
    return emit_exit(admit_live(repo=args.repo, pr=args.pr, live=read_live(args)))


if __name__ == "__main__":
    raise SystemExit(main())

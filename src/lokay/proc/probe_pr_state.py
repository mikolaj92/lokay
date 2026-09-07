"""Atomic: view one PR state (read-only). Fail-open on gh flake."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.gh_prs import gh_json
from lokay.proc._common import add_config_read, read_live, runner


def classify_view(row: dict[str, Any] | None, *, pr: int) -> dict[str, Any]:
    """Map gh pr view JSON to open | merged | closed | unavailable."""
    if not isinstance(row, dict) or not row:
        return ok(
            route="unavailable",
            reason="pr_view_empty",
            pr=pr,
            state="",
            merged=False,
        )
    state = str(row.get("state") or "").upper()
    merged_at = row.get("mergedAt")
    merged = bool(merged_at) or state == "MERGED"
    if merged:
        route = "merged"
        reason = "pr_already_merged"
    elif state == "CLOSED":
        route = "closed"
        reason = "pr_closed"
    elif state == "OPEN" or not state:
        # Empty state treated as open only when mergedAt absent and live view ok.
        route = "open" if state == "OPEN" else "unavailable"
        reason = "pr_open" if route == "open" else "pr_state_unknown"
    else:
        route = "unavailable"
        reason = f"pr_state_{state.lower() or 'unknown'}"
    return ok(
        route=route,
        reason=reason,
        pr=int(row.get("number") or pr),
        state="MERGED" if merged else state,
        merged=merged,
        merged_at=str(merged_at or ""),
        head_ref=str(row.get("headRefName") or ""),
    )


def probe(*, repo: str, pr: int, live: bool) -> dict[str, Any]:
    if not live:
        return ok(
            route="open",
            reason="offline_assume_open",
            offline=True,
            repo=repo,
            pr=pr,
            state="OPEN",
            merged=False,
        )
    try:
        row = gh_json(
            runner(),
            [
                "pr",
                "view",
                str(pr),
                "--repo",
                repo,
                "--json",
                "state,mergedAt,number,headRefName",
            ],
            live=True,
        )
    except Exception as exc:  # noqa: BLE001 — fail-open like issue mid-flight
        return ok(
            route="unavailable",
            reason="pr_view_failed",
            probe_failed=True,
            error=str(exc),
            repo=repo,
            pr=pr,
            state="",
            merged=False,
        )
    out = classify_view(row if isinstance(row, dict) else None, pr=pr)
    out["repo"] = repo
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-probe-pr-state")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    args = p.parse_args(argv)
    return emit_exit(probe(repo=args.repo, pr=args.pr, live=read_live(args)))


if __name__ == "__main__":
    raise SystemExit(main())

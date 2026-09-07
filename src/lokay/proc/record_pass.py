"""One job: write a small last-pass receipt (new_pr / merge / none)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.passkit import io as pass_io
from lokay.pass_history import append_pass_receipt
from lokay.pass_receipt import write_pass_receipt
from lokay.proc._common import add_config_live

OUTCOMES = ("merge", "new_pr", "none")
_OVERFLOW = "leftover_overflow"
_DROP = frozenset({"by_repo", "candidates", "repos", "leftover_rows"})
_PUBLISHED = frozenset({"pr", "new_pr"})


def _blob(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _result(value: Any) -> dict[str, Any]:
    blob = _blob(value)
    inner = blob.get("result")
    return inner if isinstance(inner, dict) else blob


def _read_optional(path: Path) -> dict[str, Any]:
    try:
        return pass_io.read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def leftover_overflowed(*blobs: Any) -> bool:
    """Leftover overflow is a skip, never a pass failure."""
    for blob in blobs:
        row = _blob(blob)
        if not row:
            continue
        if row.get("reason") == _OVERFLOW:
            return True
        if _OVERFLOW in str(row.get("error") or ""):
            return True
        if leftover_overflowed(row.get("result")):
            return True
    return False


def classify_outcome(
    *,
    prs: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    working: dict[str, Any] | None = None,
    tick: dict[str, Any] | None = None,
) -> str:
    """One receipt word: merge, new_pr, or none. Merge wins (Done)."""
    prs_r = _result(prs)
    issues_r = _result(issues)
    working = _blob(working)
    triage = _result(prs_r.get("triage") or prs_r.get("triaged"))
    merged = (
        bool(prs_r.get("merged"))
        or bool(_blob(prs).get("merged"))
        or bool(triage.get("merged"))
        or str(prs_r.get("route") or "") == "merged"
        or str(prs_r.get("triaged") or "") == "merged"
        or bool(working.get("merged_this_pass"))
    )
    if merged:
        return "merge"
    launched = str(issues_r.get("launched") or "")
    if launched in _PUBLISHED:
        return "new_pr"
    return "none"


def occupancy_started(
    *,
    issues: dict[str, Any] | None = None,
    working: dict[str, Any] | None = None,
    tick: dict[str, Any] | None = None,
) -> int:
    """Detached coding occupies the slot. That is not a published PR."""
    issues_r = _result(issues)
    working = _blob(working)
    rem = _blob(tick).get("remaining")
    rem = rem if isinstance(rem, dict) else {}
    started = int(working.get("issue_to_pr_started") or rem.get("issue_to_pr_started") or 0)
    if str(issues_r.get("launched") or "") == "started":
        return max(started, 1)
    return started


def _state_path(begin: dict[str, Any], pass_dir: str) -> Path:
    raw = str(begin.get("state_path") or "")
    if raw:
        return Path(raw)
    if pass_dir:
        return Path(pass_dir).expanduser().resolve() / "state.jsonl"
    return Path.home() / ".lokay" / "state.jsonl"


def _occupied_repos_for_leftover(
    working: dict[str, Any] | None, issues: dict[str, Any] | None
) -> set[str]:
    """Repos with a live i2pr must not appear as leftover ready (#1017)."""
    working = _blob(working)
    occupied = {
        str(name)
        for name in list(working.get("occupied_repos") or [])
        + list(working.get("live_issue_to_pr_repos") or [])
        if name
    }
    issues_r = _result(issues)
    if str(issues_r.get("launched") or issues_r.get("route") or "") in {
        "started",
        "busy",
    }:
        repo = str(issues_r.get("repo") or "")
        if repo:
            occupied.add(repo)
    return occupied


def _prior_leftover_issues(remaining: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in list(remaining.get("leftover_issues") or [])
        if isinstance(row, dict)
    ]


def _issues_leftover_remaining(
    issues: dict[str, Any] | None,
    remaining: dict[str, Any],
    *,
    working: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Skip / triage_not_done must not wipe leftover. Count stays on last-pass.

    Live issue_to_pr occupancy removes that repo from leftover ready (#1017).
    Occupancy alone must not cold-wipe non-occupied leftover fuel (#1067).
    """
    issues_r = _result(issues)
    occupied = _occupied_repos_for_leftover(working, issues)
    raw_issues = [
        row for row in list(issues_r.get("leftover_issues") or []) if isinstance(row, dict)
    ]

    def _unoccupied(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if str(row.get("repo") or "") not in occupied]

    prior = _unoccupied(_prior_leftover_issues(remaining))
    if raw_issues:
        # Fresh leftover list this pass — occupancy filters only (#1017).
        leftover_issues = _unoccupied(raw_issues)
        if leftover_issues:
            leftover = len(leftover_issues)
        elif prior:
            # Occupancy emptied the fresh list; keep non-occupied prior fuel
            # (#1071). Ready occupancy must not cold-wipe other repos.
            leftover_issues = prior
            leftover = len(leftover_issues)
        else:
            leftover = 0
    else:
        # Empty/missing leftover_issues. Occupancy or skip must not cold-wipe
        # prior non-occupied fuel from the receipt (#1067).
        if prior:
            leftover_issues = prior
            leftover = len(leftover_issues)
        else:
            leftover_issues = []
            try:
                leftover = int(
                    remaining.get("leftover")
                    or issues_r.get("leftover")
                    or 0
                )
            except (TypeError, ValueError):
                leftover = 0
            # Explicit empty list without prior fuel: trust zero.
            if not occupied and "leftover_issues" in issues_r:
                leftover = 0
    out = {**remaining, "leftover": leftover}
    if leftover_issues:
        out["leftover_issues"] = leftover_issues
    else:
        out.pop("leftover_issues", None)
    if str(issues_r.get("route") or "") == "skip" and issues_r.get("issue") is not None:
        out["skipped_issue"] = issues_r.get("issue")
        out["skipped_repo"] = issues_r.get("repo")
    return out


def _small_remaining(tick: dict[str, Any], *, overflow: bool) -> dict[str, Any]:
    rem = tick.get("remaining") if isinstance(tick.get("remaining"), dict) else {}
    if overflow:
        count = rem.get("count")
        out = {_OVERFLOW: True}
        if count is not None:
            out["count"] = count
        return out
    return {key: rem[key] for key in rem if key not in _DROP}


def run_record_pass(
    *,
    pass_dir: str = "",
    begin: dict[str, Any] | None = None,
    prs: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    leftover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    disk_begin = _read_optional(pass_io.begin_path(pass_dir)) if pass_dir else {}
    tick = _read_optional(pass_io.tick_path(pass_dir)) if pass_dir else {}
    working = _read_optional(pass_io.working_path(pass_dir)) if pass_dir else {}
    begin = {**disk_begin, **_blob(begin)}
    overflow = leftover_overflowed(leftover, tick, working, prs, issues, begin)
    outcome = classify_outcome(prs=prs, issues=issues, working=working, tick=tick)
    started = occupancy_started(issues=issues, working=working, tick=tick)
    seed = _small_remaining(tick, overflow=overflow)
    # compute_health rebuilds remaining without leftover; seed from last-pass
    # so occupancy-without-relist cannot cold-wipe catalog memory (#1067).
    # leftover:0 alone must not block leftover_issues reseeding (#1071).
    if "leftover_issues" not in seed:
        try:
            from lokay.pass_receipt import read_pass_receipt

            prior = read_pass_receipt(state_path=_state_path(begin, pass_dir))
        except Exception:
            prior = None
        prior_rem = prior.get("remaining") if isinstance(prior, dict) else None
        if isinstance(prior_rem, dict):
            if "leftover_issues" in prior_rem:
                seed["leftover_issues"] = prior_rem["leftover_issues"]
            if "leftover" not in seed and "leftover" in prior_rem:
                seed["leftover"] = prior_rem["leftover"]
    remaining = _issues_leftover_remaining(
        issues,
        seed,
        working=working,
    )
    if started:
        remaining = {**remaining, "issue_to_pr_started": started}
    leftover_n = int(remaining.get("leftover") or 0)
    progress = int(tick.get("progress") or 0)
    productive = outcome != "none" or started > 0
    if productive:
        progress = max(progress, 1)
    health = str(tick.get("health") or ("progress" if productive else "idle"))
    if leftover_n and health in {"", "idle"}:
        health = "waiting"
    if overflow and health in {"", "idle"}:
        health = "waiting"
    receipt = {
        "kind": "pass_receipt",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome,
        "ok": True,
        "health": health,
        "idle": bool(
            outcome == "none"
            and not overflow
            and leftover_n == 0
            and started == 0
            and tick.get("idle", outcome == "none")
        ),
        "live": bool(begin.get("live", tick.get("live"))),
        "progress": progress,
        "lane": str(tick.get("lane") or ("product" if productive else "idle")),
        "config": begin.get("config_path"),
        "remaining": remaining,
        _OVERFLOW: overflow,
    }
    result = {
        "ok": True,
        "health": health,
        "outcome": outcome,
        "lane": receipt["lane"],
        "progress": progress,
        "idle": receipt["idle"],
        "remaining": remaining,
        _OVERFLOW: overflow,
    }
    try:
        state_path = _state_path(begin, pass_dir)
        written = write_pass_receipt(receipt, state_path=state_path)
        append_pass_receipt(receipt, state_path=state_path)
        result["pass_receipt_path"] = str(written)
        if pass_dir:
            payload = {**tick, **result}
            pass_io.write_json(pass_io.tick_path(pass_dir), payload)
    except OSError as exc:
        result["pass_receipt_error"] = str(exc)
    return ok(pass_dir=pass_dir, outcome=outcome, tick=result, result=result)


def record(
    *,
    pass_dir: str = "",
    begin: dict[str, Any] | None = None,
    prs: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    leftover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_record_pass(
        pass_dir=pass_dir,
        begin=begin,
        prs=prs,
        issues=issues,
        leftover=leftover,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-record-pass")
    add_config_live(parser)
    parser.add_argument("--pass-dir", default="")
    args = parser.parse_args(argv)
    return emit_exit(run_record_pass(pass_dir=str(args.pass_dir or "")))


if __name__ == "__main__":
    raise SystemExit(main())

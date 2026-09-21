"""One job: write a small last-pass receipt (new_pr / merge / none)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.passkit import io as pass_io
from lokay.pass_history import append_pass_receipt
from lokay.pass_receipt import write_pass_receipt
from lokay.proc._common import add_config_live
from lokay.proc.walk_pr_leftover import skipped_fields

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


_PR_EVIDENCE = (
    "ok", "route", "verdict", "reason", "repo", "pr", "branch", "head_sha",
    "reviewed_head_sha", "repair_start_head_sha", "repair_kind", "merged",
    "terminal", "repaired", "published", "repair_push_intent_sha256",
    "attempts", "budget", "parked", "root_reason",
)
_PR_FLAGS = frozenset({"ok", "merged", "repaired", "published", "parked"})
_PR_COUNTS = frozenset({"pr", "attempts", "budget"})


def _typed_pr_fields(value: Any) -> dict[str, Any]:
    """Project domain scalars, never stringify a transport terminal or logs.

    Oversized strings are omitted, not truncated: identity must remain exact.
    Full evidence belongs to the referenced Fala journal, not the receipt.
    """
    out = {}
    for key, item in _blob(value).items():
        if key not in _PR_EVIDENCE:
            continue
        if key in _PR_FLAGS:
            valid = type(item) is bool
        elif key in _PR_COUNTS:
            valid = type(item) is int and 0 <= item < 2**63
        else:
            valid = isinstance(item, str) and len(item) <= 1024
        if valid:
            out[key] = item
    return out


def _pr_evidence(value: Any, *, child: str) -> dict[str, Any]:
    parent = _result(value)
    raw_detail = _blob(parent.get(child))
    detail = {**_typed_pr_fields(raw_detail),
              **_typed_pr_fields(raw_detail.get("result"))}
    combined = {**detail, **_typed_pr_fields(parent)}
    if child == "repair" and raw_detail:
        failed = raw_detail.get("ok") is False or detail.get("ok") is False
        if failed:
            # A transport failure cannot be made published by a partial summary.
            combined.update(ok=False, repaired=False, published=False)
            combined.setdefault("terminal", "failed")
        root_reason = detail.get("reason")
        if failed and not root_reason:
            # Native subprocess failures wrap the organ's JSON in an adapter
            # message. Read only that final bounded envelope, never its logs.
            error = raw_detail.get("error")
            message = _blob(error).get("message") if isinstance(error, dict) else error
            if isinstance(message, str):
                encoded = message[-2000:].rsplit("RuntimeError: ", 1)[-1].strip()
                try:
                    envelope = _blob(json.loads(encoded))
                    failure = {**_typed_pr_fields(envelope),
                               **_typed_pr_fields(envelope.get("result"))}
                except (ValueError, TypeError):
                    failure = {}
                root_reason = failure.get("reason")
                if failure.get("head_sha"):
                    combined["head_sha"] = failure["head_sha"]
        if root_reason:
            combined["root_reason"] = root_reason
        trace = {key: raw_detail[key] for key in ("db", "run_id", "path_id")
                 if isinstance(raw_detail.get(key), str) and 0 < len(raw_detail[key]) <= 1024}
        if trace:
            combined["trace"] = trace
    return combined


def _skip_remaining(remaining: dict, prior: dict | None = None) -> dict:
    """Migrate only unambiguous legacy tuples, never splice their components."""
    prior = prior or {}
    out = dict(remaining)
    for key in ("skipped_repo", "skipped_pr_repo", "skipped_pr", "skipped_head_sha",
                "skipped_issue_repo", "skipped_issue"):
        out.pop(key, None)
    out.update(skipped_fields(remaining) or skipped_fields(prior))
    for source in (remaining, prior):
        repo = source.get("skipped_issue_repo")
        if "skipped_issue_repo" not in source and source.get("skipped_pr") is None:
            repo = source.get("skipped_repo")
        if repo and source.get("skipped_issue") is not None:
            out.update(skipped_issue_repo=repo, skipped_issue=source["skipped_issue"])
            break
    return out


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


def _prior_leftover_prs(remaining: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in list(remaining.get("leftover_prs") or [])
        if isinstance(row, dict)
    ]


def _prs_leftover_remaining(
    prs: dict[str, Any] | None,
    remaining: dict[str, Any],
) -> dict[str, Any]:
    """Skip / fail_closed leftover_prs stay on last-pass. Missing key keeps prior."""
    prs_r = _result(prs)
    raw_prs = [
        row for row in list(prs_r.get("leftover_prs") or []) if isinstance(row, dict)
    ]
    prior = _prior_leftover_prs(remaining)
    leftover_listed = "leftover_prs" in prs_r
    if leftover_listed:
        leftover_prs = raw_prs
    elif prior:
        leftover_prs = prior
    else:
        leftover_prs = []
    out = dict(remaining)
    if leftover_prs:
        out["leftover_prs"] = leftover_prs
    elif leftover_listed:
        out["leftover_prs"] = []
    elif prior:
        out["leftover_prs"] = prior
    out = _skip_remaining(out)
    out.update(skipped_fields(prs_r))
    return out


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
        # Empty/missing leftover_issues. Occupancy or a missing list must not
        # cold-wipe prior non-occupied fuel from the receipt (#1067). An
        # explicit leftover_issues=[] with leftover=0 and no occupancy is a
        # consumed queue (host_ops skip); do not reseed the same tickets.
        leftover_listed = "leftover_issues" in issues_r
        try:
            leftover_n = int(issues_r.get("leftover") or 0)
        except (TypeError, ValueError):
            leftover_n = 0
        consumed = leftover_listed and leftover_n == 0 and not occupied
        if prior and not consumed:
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
            if consumed or (not occupied and leftover_listed):
                leftover = 0
    out = {**_skip_remaining(remaining), "leftover": leftover}
    if leftover_issues:
        out["leftover_issues"] = leftover_issues
    else:
        out.pop("leftover_issues", None)
    if (str(issues_r.get("route") or "") == "skip"
            and issues_r.get("issue") is not None and issues_r.get("repo")):
        out.update(skipped_issue=issues_r["issue"], skipped_issue_repo=issues_r["repo"])
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
    repair: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    leftover: dict[str, Any] | None = None,
    host_gate: dict[str, Any] | None = None,
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
    from lokay.pass_receipt import read_pass_receipt

    prior = read_pass_receipt(state_path=_state_path(begin, pass_dir))
    prior_rem = _blob(_blob(prior).get("remaining"))
    seed = _skip_remaining(seed, prior_rem)
    for key in ("leftover_issues", "leftover", "leftover_prs"):
        if key not in seed and key in prior_rem:
            seed[key] = prior_rem[key]
    remaining = _issues_leftover_remaining(
        issues,
        seed,
        working=working,
    )
    remaining = _prs_leftover_remaining(prs, remaining)
    if started:
        remaining = {**remaining, "issue_to_pr_started": started}
    leftover_n = int(remaining.get("leftover") or 0) + len(
        _prior_leftover_prs(remaining)
    )
    triage_evidence = _pr_evidence(prs, child="triage")
    repair_evidence = _pr_evidence(repair, child="repair")
    repair_blocked = bool(repair_evidence) and (
        repair_evidence.get("route") in {"fail_closed", "blocked", "failed"}
        or repair_evidence.get("terminal") == "blocked"
        or repair_evidence.get("ok") is False
    )
    repair_head = str(repair_evidence.get("head_sha") or "")
    repair_start = str(repair_evidence.get("repair_start_head_sha")
                       or repair_evidence.get("reviewed_head_sha") or "")
    repair_pushed = (
        not repair_blocked and repair_evidence.get("route") == "completed"
        and repair_evidence.get("terminal") == "publish"
        and repair_evidence.get("published") is True
        and repair_evidence.get("repaired") is True
        and bool(repair_evidence.get("repo") and repair_evidence.get("pr"))
        and bool(re.fullmatch(r"[a-fA-F0-9]{40}", repair_head))
        and bool(re.fullmatch(r"[a-fA-F0-9]{40}", repair_start))
        and repair_head.lower() != repair_start.lower()
    )
    evidence = {}
    if triage_evidence:
        evidence["pr_triage"] = triage_evidence
    if repair_evidence:
        evidence["pr_repair"] = repair_evidence
    if repair_blocked:
        evidence.update(ok=False, reason=str(repair_evidence.get("reason")
                                            or repair_evidence.get("terminal")
                                            or "pr_repair_failed"))
    progress = int(tick.get("progress") or 0)
    productive = outcome != "none" or started > 0 or repair_pushed
    if productive:
        progress = max(progress, 1)
    health = str(tick.get("health") or ("progress" if productive else "idle"))
    if leftover_n and health in {"", "idle"}:
        health = "waiting"
    if overflow and health in {"", "idle"}:
        health = "waiting"
    if repair_blocked:
        health = "pr_repair_blocked"
    elif repair_pushed and outcome == "none":
        health = "repairing"
    receipt = {
        "kind": "pass_receipt",
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome,
        "ok": True,
        "health": health,
        "idle": bool(
            outcome == "none"
            and not overflow
            and leftover_n == 0
            and started == 0
            and not repair_blocked
            and not repair_pushed
            and tick.get("idle", outcome == "none")
        ),
        "live": bool(begin.get("live", tick.get("live"))),
        "progress": progress,
        "lane": "product" if repair_blocked or repair_pushed else str(
            tick.get("lane") or ("product" if productive else "idle")
        ),
        "config": begin.get("config_path"),
        "remaining": remaining,
        _OVERFLOW: overflow,
        **evidence,
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
        **evidence,
    }
    from lokay.host_gate import stopped

    stop = stopped(host_gate or {})
    receipt.update(stop)
    result.update(stop)
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
    out = ok(pass_dir=pass_dir, outcome=receipt["outcome"], tick=result, result=result)
    if stop:
        # Recording succeeded; the host failure/restart remains visible to
        # native graph consumers without turning this recording atom failed.
        out.update({key: value for key, value in stop.items() if key != "ok"})
    return out


def record(
    *,
    pass_dir: str = "",
    begin: dict[str, Any] | None = None,
    prs: dict[str, Any] | None = None,
    repair: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    leftover: dict[str, Any] | None = None,
    host_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_record_pass(
        pass_dir=pass_dir,
        begin=begin,
        prs=prs,
        repair=repair,
        issues=issues,
        leftover=leftover,
        host_gate=host_gate,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-record-pass")
    add_config_live(parser)
    parser.add_argument("--pass-dir", default="")
    args = parser.parse_args(argv)
    return emit_exit(run_record_pass(pass_dir=str(args.pass_dir or "")))


if __name__ == "__main__":
    raise SystemExit(main())

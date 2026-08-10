"""Dedicated, bounded Lokay self-repair lane.

This lane is entered only after deterministic preflight repair failed.  It never
surveys product intake: the one incident URL produced by preflight is its sole
unit of work.  The running (last-known-good) Lokay process deterministically
owns GitHub/merge/deploy decisions while Fala is used only for the existing
issue_to_pr, pr_repair and pr_triage paths.
"""
from __future__ import annotations

import json
import re
import subprocess
import os
import time
from pathlib import Path
from typing import Any

from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.compose.pr_repair import compose_pr_repair
from lokay.compose.pr_triage import compose_pr_triage
from lokay.config import load_config
from lokay.state import append_event

SELF_REPAIR_REPO = "mikolaj92/lokay"
_ISSUE_URL = re.compile(r"^https://github\.com/mikolaj92/lokay/issues/(\d+)$")


def _event(cfg: Any, **event: Any) -> None:
    try: append_event(cfg.state_path, {"kind": "self_repair", **event})
    except Exception: pass


def _gh_json(args: list[str]) -> Any:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
        timeout=60, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("GitHub operation unavailable")
    return json.loads(result.stdout or "null")


def _incident_number(preflight: dict[str, Any]) -> int | None:
    match = _ISSUE_URL.fullmatch(str(preflight.get("incident_url") or ""))
    return int(match.group(1)) if match else None


def _repair_pr(issue: int, *, fingerprint: str, branch_prefix: str = "ai/fix") -> dict[str, Any] | None:
    rows = _gh_json([
        "pr", "list", "--repo", SELF_REPAIR_REPO, "--state", "open",
        "--json", "number,headRefName,headRefOid,headRepository,baseRefName,body,mergeable", "--limit", "50",
    ])
    if not isinstance(rows, list):
        raise RuntimeError("malformed GitHub PR response")
    # Branch names are deterministic and begin <prefix>/<issue>-.  Restricting
    # by issue prevents an unrelated Lokay PR from entering the repair lane.
    prefix = f"{branch_prefix.rstrip('/')}/{issue}-"
    marker = f"<!-- lokay-preflight:{fingerprint} -->"
    matches = [row for row in rows if
        str(row.get("headRefName") or "").startswith(prefix)
        and str(row.get("baseRefName") or "") == "main"
        and str(((row.get("headRepository") or {}).get("nameWithOwner") or "")) == SELF_REPAIR_REPO
        and marker in str(row.get("body") or "")]
    if len(matches) > 1:
        raise RuntimeError("ambiguous repair PRs")
    return dict(matches[0]) if matches else None


def _checks(pr: int, *, require_checks: bool) -> str:
    result = subprocess.run(
        ["gh", "pr", "checks", str(pr), "--repo", SELF_REPAIR_REPO],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
        check=False,
    )
    text = ((result.stdout or "") + "\n" + (result.stderr or "")).lower()
    if "no checks reported" in text:
        return "blocked" if require_checks else "passed"
    if result.returncode == 0: return "passed"
    if result.returncode == 8 or "pending" in text or "in_progress" in text: return "pending"
    return "failed"


def _activate(cfg: Any, *, expected_commit: str) -> dict[str, Any]:
    """Fast-forward the configured Lokay checkout, but never touch dirty state."""
    repo = next((r for r in cfg.active_repos() if r.name == SELF_REPAIR_REPO), None)
    if repo is None or not repo.clone_path.is_dir():
        return {"ok": False, "activated": False, "reason": "lokay_clone_unavailable"}
    origin = subprocess.run(["git", "-C", str(repo.clone_path), "remote", "get-url", "origin"], capture_output=True, text=True, timeout=30, check=False)
    if origin.returncode or "mikolaj92/lokay" not in origin.stdout:
        return {"ok": False, "activated": False, "reason": "wrong_origin"}
    commands = [
        ["git", "-C", str(repo.clone_path), "status", "--porcelain"],
        ["git", "-C", str(repo.clone_path), "fetch", "origin", "main"],
        ["git", "-C", str(repo.clone_path), "merge", "--ff-only", "origin/main"],
    ]
    first = subprocess.run(commands[0], capture_output=True, text=True, timeout=30, check=False)
    if first.returncode or first.stdout.strip():
        return {"ok": False, "activated": False, "reason": "lokay_clone_not_clean"}
    for command in commands[1:]:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False)
        if result.returncode:
            return {"ok": False, "activated": False, "reason": "fast_forward_failed"}
    ancestor = subprocess.run(["git", "-C", str(repo.clone_path), "merge-base", "--is-ancestor", expected_commit, "HEAD"], timeout=30, check=False)
    if ancestor.returncode:
        return {"ok": False, "activated": False, "reason": "exact_merge_not_activated"}
    return {"ok": True, "activated": True, "path": str(repo.clone_path), "commit": expected_commit}


def run_self_repair(
    config_path: str | None,
    preflight: dict[str, Any],
    *,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """Service exactly the deduplicated preflight incident, or fail closed."""
    cfg = load_config(config_path)
    issue = _incident_number(preflight)
    budget = max(1, min(int(max_attempts if max_attempts is not None else cfg.max_self_repair_attempts), 3))
    result: dict[str, Any] = {
        "ok": False, "health": "self_repair_failed", "issue": issue,
        "incident_url": preflight.get("incident_url"), "attempts": [],
        "gate_released": False,
    }
    _event(cfg, phase="start", fingerprint=preflight.get("fingerprint"), issue=issue, budget=budget)
    failed_names = {x.get("name") for x in preflight.get("findings", []) if not x.get("ok")}
    if not preflight.get("carrier_ok"):
        result["reason"] = "carrier_unhealthy"
        _event(cfg, phase="blocked", reason=result["reason"]); return result
    if issue is None:
        result["reason"] = "deduplicated_incident_unavailable"
        _event(cfg, phase="blocked", reason=result["reason"]); return result
    if "github_authentication" in failed_names or "executor_availability" in failed_names:
        result["reason"] = "bootstrap_dependency_unavailable"
        _event(cfg, phase="blocked", reason=result["reason"]); return result
    if not cfg.executor_enabled:
        result["reason"] = "executor_disabled"
        _event(cfg, phase="blocked", reason=result["reason"]); return result

    # Carrier preflight issued the ordinary health lease.  Every live Fala atom
    # uses the same normal gate as product work; there is no repair bypass.
    deadline = time.monotonic() + min(max(60, cfg.whole_run_deadline_seconds), 3600)
    try:
        for attempt in range(1, budget + 1):
            row: dict[str, Any] = {"attempt": attempt}
            result["attempts"].append(row)
            try: pr = _repair_pr(issue, fingerprint=str(preflight.get("fingerprint") or ""), branch_prefix=cfg.branch_prefix)
            except Exception:
                row.update(ok=False, phase="discover_pr", reason="github_unavailable"); break
            if pr is None:
                made = compose_issue_to_pr(config_path=config_path, repo=SELF_REPAIR_REPO, issue_number=issue, live=True)
                row["issue_to_pr"] = made
                if not made.get("ok"):
                    row.update(ok=False, phase="issue_to_pr"); continue
                pr_number = made.get("pr")
                branch = str(made.get("branch") or "")
                if not pr_number or not branch:
                    # A successful zero-diff executor run is not a repair.
                    row.update(ok=False, phase="issue_to_pr", reason="zero_diff_or_no_pr"); continue
                pr = {"number": int(pr_number), "headRefName": branch}
            pr_number = int(pr["number"]); branch = str(pr.get("headRefName") or "")
            identity = _gh_json(["pr", "view", str(pr_number), "--repo", SELF_REPAIR_REPO, "--json", "headRefName,headRefOid,headRepository,baseRefName,body"])
            head_sha = str(identity.get("headRefOid") or "")
            marker = f"<!-- lokay-preflight:{preflight.get('fingerprint')} -->"
            if (str(identity.get("headRefName") or "") != branch or not head_sha
                or str(identity.get("baseRefName") or "") != "main"
                or str(((identity.get("headRepository") or {}).get("nameWithOwner") or "")) != SELF_REPAIR_REPO
                or marker not in str(identity.get("body") or "")):
                row.update(ok=False, phase="pr_identity"); break
            row.update(pr=pr_number, branch=branch, head_sha=head_sha)
            status = _checks(pr_number, require_checks=cfg.require_checks)
            row["checks"] = status
            if status == "failed":
                repaired = compose_pr_repair(config_path=config_path, repo=SELF_REPAIR_REPO, pr_number=pr_number, branch=branch, live=True)
                row["pr_repair"] = repaired
                # Validation always occurs on a later bounded attempt/fresh query.
                continue
            if status != "passed":
                row.update(ok=False, phase="validation", reason=status); break
            if not cfg.merge_enabled:
                row.update(ok=False, phase="merge", reason="merge_policy_disabled"); break
            triaged = compose_pr_triage(config_path=config_path, repo=SELF_REPAIR_REPO, pr_number=pr_number, branch=branch, live=True, keep_issue_open=True)
            row["pr_triage"] = triaged
            if not triaged.get("ok") or not triaged.get("merged"):
                row.update(ok=False, phase="normal_merge_policy"); continue
            merged = _gh_json(["pr", "view", str(pr_number), "--repo", SELF_REPAIR_REPO, "--json", "mergeCommit,headRefName,headRepository"])
            merge_commit = str(((merged or {}).get("mergeCommit") or {}).get("oid") or "")
            if not merge_commit or str(merged.get("headRefName") or "") != branch:
                row.update(ok=False, phase="merged_identity"); break
            activation = _activate(cfg, expected_commit=merge_commit); row["activation"] = activation
            if not activation.get("ok"):
                row.update(ok=False, phase="activation"); break
            check = subprocess.run(
                ["uv", "run", "--project", str(activation["path"]), "lokay-preflight",
                 "--config", str(config_path), "--no-repair"],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                timeout=180, check=False,
                env={**__import__("os").environ, "LOKAY_HEALTH_LEASE": "",
                     "LOKAY_SELF_REPAIR_ATOM": "", "LOKAY_SELF_REPAIR_VALIDATION": "1"},
            )
            try: health = json.loads((check.stdout or "").strip().splitlines()[-1])
            except (ValueError, IndexError): health = {"ok": False, "health": "validation_failed"}
            row["preflight"] = {"ok": bool(check.returncode == 0 and health.get("ok")), "health": health.get("health")}
            if row["preflight"]["ok"]:
                closed = subprocess.run(["gh", "issue", "close", str(issue), "--repo", SELF_REPAIR_REPO,
                    "--comment", f"Validated repair PR #{pr_number} for fingerprint {preflight.get('fingerprint')}."],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=30, check=False)
                row["incident_closed"] = closed.returncode == 0
                if closed.returncode != 0:
                    row.update(ok=False, phase="incident_close"); result["reason"] = "validated_but_close_failed"; break
                result.update(ok=True, health="restart_required", gate_released=False, validated=True, repaired_pr=pr_number, activation=activation, incident_closed=True)
                _event(cfg, phase="validated_restart_required", issue=issue, pr=pr_number, activation=activation)
                return result
        result["reason"] = result.get("reason") or "repair_budget_exhausted"
        _event(cfg, phase="failed", issue=issue, attempts=len(result["attempts"]), reason=result["reason"])
        return result
    finally:
        pass

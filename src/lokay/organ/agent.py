"""Fala organ routing — one job family per module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.organ.common import (
    _cfg_flags,
    _live_flags,
    _localize_paths,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _run_atom_main,
    _test_local_ok,
)
from lokay.prompts import (
    issue_fix_prompt,
    local_test_repair_prompt,
    pr_body,
    repair_pr_prompt,
    self_repair_prompt,
)


def handle_agent(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    from lokay.proc import (
        assign_issue, close_issue, commit_all, closeout_prs, compute_health,
        cycle_end, cycle_start, dispatch_implement, dispatch_triage, factory_begin,
        factory_tick, get_issue, host_ff, list_prs, make_branch, plan_issue,
        localize, pi_budget, plan_pass, pr_checks, pr_create, pr_label, pr_merge,
        pr_review, push_branch, record_pass, recovery_begin, recovery_incident,
        recovery_mill, recovery_observe, recovery_record, recovery_run_self_repair,
        resolve_conflicts, run_agent, select_implement, queue_conflict, stage_label,
        survey_inbox, survey_prs, survey_ready, survey_repos, test_local,
        triage_issue, intake_issue, issue_split, worktree_add, assert_real_diff,
        self_repair_activate, self_repair_close, self_repair_prepare,
        self_repair_preflight, self_repair_push_main, self_repair_validate,
    )
    from lokay.git_commit import branch_ahead_of_upstream
    from lokay.proc._common import runner
    from lokay.stuck import issue_number_from_branch
    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]

    import lokay.fala_organ as _fo
    _run_atom_main = _fo._run_atom_main
    branch_ahead_of_upstream = getattr(_fo, "branch_ahead_of_upstream", None)
    if branch_ahead_of_upstream is None:
        from lokay.git_commit import branch_ahead_of_upstream

    if atom == "run_agent":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        )
        assert worktree
        # Fail-closed: localize must produce a non-empty path list before agent.
        if "localize" not in up:
            return {
                "ok": False,
                "error": "refusing run_agent: localize conduction missing",
                "reason": "localize_missing",
            }
        paths = _localize_paths(up)
        if not paths:
            return {
                "ok": False,
                "error": "refusing run_agent: localize produced no edit paths",
                "reason": "localize_empty",
                "localize": up.get("localize") or {},
            }
        if repair_mode:
            assert pr_number is not None and branch
            checks_text = str(
                up.get("pr_checks", {}).get("text")
                or inputs.get("checks_text")
                or ""
            )
            prompt = repair_pr_prompt(
                repo=repo,
                pr_number=pr_number,
                branch=branch,
                checks_text=checks_text,
                review_text=json.dumps(inputs.get("review") or {}, ensure_ascii=False, sort_keys=True),
                paths=paths,
            )
        else:
            issue_raw = up.get("get_issue", {}).get("issue") or {}
            issue = Issue.from_dict(issue_raw) if issue_raw else None
            assert issue is not None
            prompt = issue_fix_prompt(issue, branch=branch, paths=paths)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(prompt)
            prompt_path = fh.name
        try:
            return _run_atom_main(
                run_agent.main,
                [*cfg, *live, "--worktree", worktree, "--prompt-file", prompt_path],
            )
        finally:
            Path(prompt_path).unlink(missing_ok=True)

    if atom == "repair_agent":
        # AlphaCodium bounded loop, K=1: exactly one extra patch after a red
        # local suite. Any other state is a no-op; test_local_recheck reruns
        # pytest once after this, and push/pr_create never see a red suite.
        if repair_mode:
            # pr_repair already IS the repair lane — no nested repair session.
            return {
                "ok": False,
                "error": "refusing: repair_agent is issue_to_pr-only",
                "reason": "repair_agent_not_allowed",
            }
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        first = up.get("test_local")
        if first is None:
            return {
                "ok": False,
                "error": "refusing: test_local conduction missing",
                "reason": "test_local_missing",
            }
        if _test_local_ok(first):
            return {"ok": True, "skipped": True, "reason": "test_local_ok"}
        log_text = "\n".join(
            tail
            for tail in (
                str(first.get("stdout_tail") or ""),
                str(first.get("stderr_tail") or ""),
            )
            if tail.strip()
        ) or str(first.get("error") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        prompt = local_test_repair_prompt(
            repo=repo,
            branch=branch,
            issue_number=issue_number,
            issue_title=str(issue_raw.get("title") or ""),
            log_text=log_text,
        )
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(prompt)
            prompt_path = fh.name
        try:
            out = _run_atom_main(
                run_agent.main,
                [*cfg, *live, "--worktree", worktree, "--prompt-file", prompt_path],
            )
        finally:
            Path(prompt_path).unlink(missing_ok=True)
        if isinstance(out, dict):
            out["attempted"] = True
        return out

    if atom == "test_local_recheck":
        # Second (final) probe of the bounded loop: rerun pytest only after a
        # red first probe. A red recheck fails closed here — there is no third
        # attempt, so push/pr_create downstream stay unreachable.
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        first = up.get("test_local")
        if first is None:
            return {
                "ok": False,
                "error": "refusing: test_local conduction missing",
                "reason": "test_local_missing",
            }
        if _test_local_ok(first):
            return {"ok": True, "skipped": True, "reason": "test_local_ok"}
        repair = up.get("repair_agent") or {}
        if repair.get("ok") is False:
            return {
                "ok": False,
                "error": str(repair.get("error") or "repair agent failed"),
                "reason": "repair_agent_failed",
            }
        if inputs.get("live"):
            unpublished = branch_ahead_of_upstream(
                runner(), Path(worktree), live=True
            ) > 0
            committed = bool(up.get("commit_all", {}).get("committed"))
            if not (committed or unpublished):
                # Zero-diff repair: the patch nest produced nothing to test.
                return {
                    "ok": False,
                    "error": "refusing recheck: repair patch produced no commit",
                    "reason": "zero_diff",
                }
        out = _run_atom_main(test_local.main, ["--worktree", worktree])
        if isinstance(out, dict):
            if out.get("ok") is False and not out.get("skipped"):
                # Bounded loop exhausted: mark with a machine reason first, so
                # it survives the organ's truncated failure raise (the log
                # tails in this envelope can exceed the 2000-char raise cap).
                out = {
                    "ok": False,
                    "reason": "local_repair_exhausted",
                    "recheck": True,
                    **{
                        k: v
                        for k, v in out.items()
                        if k not in {"ok", "reason", "recheck"}
                    },
                }
            else:
                out["recheck"] = True
        return out

    if atom == "commit_all":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        gate = _run_atom_main(assert_real_diff.main, ["--worktree", worktree])
        if not (isinstance(gate, dict) and gate.get("real") is True):
            return {
                "ok": False,
                "error": str((gate or {}).get("error") or "refusing commit: not a real diff"),
                "reason": str((gate or {}).get("reason") or "plan_only"),
                "committed": False,
                "kind": (gate or {}).get("kind"),
            }
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        if repair_mode and pr_number is not None:
            msg = str(inputs.get("message") or f"repair: {repo} PR #{pr_number} checks")
        else:
            n = issue_raw.get("number", issue_number)
            title = str(issue_raw.get("title") or "")[:60]
            msg = str(inputs.get("message") or f"fix: {repo}#{n} {title}")
        assert worktree
        out = _run_atom_main(
            commit_all.main,
            [*cfg, *live, "--worktree", worktree, "--message", msg],
        )
        # The coding agent may commit directly (no staged diff left for the
        # deterministic commit). A clean tree with unpublished commits is real
        # progress — report it truthfully so test_local/push see the patch.
        if (
            isinstance(out, dict)
            and out.get("ok") is True
            and inputs.get("live")
            and out.get("committed") is not True
            and branch_ahead_of_upstream(runner(), Path(worktree), live=True) > 0
        ):
            out["committed"] = True
            out["committed_by"] = "agent"
        return out

    if atom == "test_local":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        out = _run_atom_main(test_local.main, ["--worktree", worktree])
        # issue_to_pr first probe: record a red suite without failing the
        # effector so Fala can conduct the one-shot repair nest. Publish
        # atoms still fail closed via _require_test_local (passed=false).
        if (
            inputs.get("record_red")
            and isinstance(out, dict)
            and out.get("ok") is False
            and not out.get("skipped")
        ):
            recorded = {
                "ok": True,
                "passed": False,
                "tested": True,
                "recorded_red": True,
                **{
                    k: v
                    for k, v in out.items()
                    if k not in {"ok", "passed", "tested", "recorded_red", "_exit"}
                },
                "_exit": 0,
            }
            return recorded
        return out

    if atom == "assert_real_diff":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        return _run_atom_main(assert_real_diff.main, ["--worktree", worktree])

    if atom == "push":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        )
        assert worktree and branch
        refused = _require_test_local(up)
        if refused is not None:
            return refused
        refused = _require_real_diff(up)
        if refused is not None:
            return refused
        committed = up.get("commit_all", {}).get("committed")
        if inputs.get("live") and committed is not True:
            # Repair agents may create commits themselves. A clean worktree with
            # unpublished commits is real progress and must still be pushed.
            unpublished = branch_ahead_of_upstream(
                runner(), Path(worktree), live=True
            ) > 0
            if not unpublished:
                return {
                    "ok": False,
                    "error": "refusing live push: no new commit to publish",
                    "reason": "zero_diff",
                    "committed": committed,
                    "worktree": worktree,
                    "branch": branch,
                }
        return _run_atom_main(
            push_branch.main,
            [*cfg, *live, "--worktree", worktree, "--branch", branch],
        )

    if atom == "pr_create":
        # Never open a PR off a red local suite, a plan-only diff, or a
        # missing/failed push.
        refused = _require_test_local(up)
        if refused is not None:
            return refused
        refused = _require_real_diff(up)
        if refused is not None:
            return refused
        refused = _require_push(up)
        if refused is not None:
            return refused
        branch = str(up.get("make_branch", {}).get("branch") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        issue = Issue.from_dict(issue_raw)
        agent = up.get("run_agent", {})
        summary = str(agent.get("stdout_tail") or agent.get("status") or "")
        body = pr_body(issue, agent_summary=summary, incident_fingerprint=str(inputs.get("incident_fingerprint") or ""))
        title = f"fix: {repo}#{issue.number} {issue.title[:72]}"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(body)
            body_path = fh.name
        try:
            return _run_atom_main(
                pr_create.main,
                [
                    *cfg,
                    *live,
                    "--repo",
                    repo,
                    "--title",
                    title,
                    "--body-file",
                    body_path,
                    "--head",
                    branch,
                ],
            )
        finally:
            Path(body_path).unlink(missing_ok=True)

    if atom == "list_prs":
        assert repo
        return _run_atom_main(list_prs.main, [*cfg, "--repo", repo])

    if atom == "pr_label":
        branch = str(up.get("make_branch", {}).get("branch") or "")
        prs = up.get("list_prs", {}).get("prs") or []
        pr_number = None
        for pr in prs:
            if pr.get("head_ref") == branch:
                pr_number = pr.get("number")
                break
        # also accept from pr_create url parse — optional
        if pr_number is None:
            return {"ok": True, "skipped": True, "reason": "pr_number_not_found", "branch": branch}
        return _run_atom_main(
            pr_label.main,
            [*cfg, *live, "--repo", repo, "--pr", str(pr_number)],
        )

    raise ValueError(f"unknown atom: {atom!r}")

    return None

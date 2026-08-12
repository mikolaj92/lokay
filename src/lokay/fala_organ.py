"""Fala subprocess organ: one atom per process, values flow via conduction.

This is the only bridge Fala → Lokay atomics. No business graph here.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fala import sdk

from lokay.git_commit import branch_ahead_of_upstream
from lokay.models import Issue
from lokay.proc._common import runner
from lokay.prompts import issue_fix_prompt, pr_body, repair_pr_prompt, self_repair_prompt


def _conduction_values(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map upstream step id → its values dict."""
    raw = sdk.conduction(manifest)
    out: dict[str, dict[str, Any]] = {}
    for step_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        values = payload.get("values")
        if isinstance(values, dict):
            out[str(step_id)] = values
        else:
            # some hosts pass values at top level
            out[str(step_id)] = payload
    return out


def _run_atom_main(module_main, argv: list[str]) -> dict[str, Any]:
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module_main(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty atom stdout", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def _cfg_flags(inputs: dict[str, Any]) -> list[str]:
    path = inputs.get("config_path") or inputs.get("config")
    return ["--config", str(path)] if path else []


def _live_flags(inputs: dict[str, Any]) -> list[str]:
    return ["--live"] if inputs.get("live") else []


def _handle(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from lokay.proc import (
        assign_issue,
        close_issue,
        commit_all,
        factory_tick,
        get_issue,
        list_prs,
        make_branch,
        pr_checks,
        pr_create,
        pr_label,
        pr_merge,
        pr_review,
        push_branch,
        recovery_begin,
        recovery_incident,
        recovery_mill,
        recovery_observe,
        recovery_record,
        recovery_run_self_repair,
        run_agent,
        triage_issue,
        intake_issue,
        issue_split,
        worktree_add,
        self_repair_activate,
        self_repair_close,
        self_repair_prepare,
        self_repair_preflight,
        self_repair_push_main,
        self_repair_validate,
    )
    from lokay.stuck import issue_number_from_branch

    cfg = _cfg_flags(inputs)
    live = _live_flags(inputs)
    repo = str(inputs.get("repo") or up.get("get_issue", {}).get("issue", {}).get("repo") or "")
    issue_number = inputs.get("issue") or inputs.get("issue_number")
    if issue_number is None and "get_issue" in up:
        issue_number = up["get_issue"].get("issue", {}).get("number")
    issue_number = int(issue_number) if issue_number is not None else None
    pr_number = inputs.get("pr") or inputs.get("pr_number")
    if pr_number is not None:
        pr_number = int(pr_number)
    repair_mode = str(inputs.get("mode") or "") == "repair"
    branch = str(
        inputs.get("branch")
        or up.get("make_branch", {}).get("branch")
        or up.get("worktree_add", {}).get("branch")
        or ""
    )

    if atom == "recovery_begin":
        return _run_atom_main(recovery_begin.main, [*cfg, *live])

    if atom == "recovery_mill":
        return _run_atom_main(
            recovery_mill.main,
            [*cfg, *live, "--max-passes", str(int(inputs.get("max_passes") or 8))],
        )

    if atom == "recovery_observe":
        begin = up.get("recovery_begin", {})
        mill = up.get("recovery_mill", {}).get("mill")
        assert begin.get("state_path") and mill is not None
        return _run_atom_main(
            recovery_observe.main,
            [
                "--state-path", str(begin["state_path"]),
                "--state-offset", str(begin.get("state_offset") or 0),
                "--mill-json", json.dumps(mill, ensure_ascii=False),
            ],
        )

    if atom == "recovery_record":
        begin = up.get("recovery_begin", {})
        observation = up.get("recovery_observe", {}).get("observation")
        assert begin.get("state_path") and observation is not None
        return _run_atom_main(
            recovery_record.main,
            [
                "--state-path", str(begin["state_path"]),
                "--observation-json", json.dumps(observation, ensure_ascii=False),
            ],
        )

    if atom == "recovery_incident":
        recorded = up.get("recovery_record", {})
        if recorded.get("confirmed") is not True:
            return {"ok": True, "skipped": True, "reason": "stall_quorum_not_met"}
        recovery = recorded.get("recovery") or {}
        return _run_atom_main(
            recovery_incident.main,
            [
                "--fingerprint", str(recovery.get("fingerprint") or ""),
                "--evidence", str(recovery.get("evidence") or ""),
            ],
        )

    if atom == "recovery_run_self_repair":
        incident = up.get("recovery_incident", {})
        if incident.get("skipped"):
            return {"ok": True, "skipped": True, "reason": incident.get("reason")}
        assert incident.get("fingerprint") and incident.get("incident_url")
        return _run_atom_main(
            recovery_run_self_repair.main,
            [
                *cfg,
                "--fingerprint", str(incident["fingerprint"]),
                "--incident-url", str(incident["incident_url"]),
                "--evidence", str(incident.get("failure_evidence") or ""),
            ],
        )

    if atom == "factory_tick":
        # Domain health (work_remaining/stall) is a successful parent effector
        # result, not a corrupt Fala execution. Preserve the complete envelope
        # and let the parent path normalizer restore its public ok/error fields.
        return {"ok": True, "tick": _run_atom_main(factory_tick.main, [*cfg, *live])}

    if atom == "self_repair_prepare":
        fingerprint = str(inputs.get("fingerprint") or "")
        assert fingerprint
        return _run_atom_main(
            self_repair_prepare.main,
            [*cfg, *live, "--fingerprint", fingerprint],
        )

    if atom == "self_repair_run_agent":
        worktree = str(up.get("self_repair_prepare", {}).get("worktree") or "")
        issue_raw = inputs.get("incident") or {}
        issue = Issue.from_dict(issue_raw) if isinstance(issue_raw, dict) else None
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and issue is not None and fingerprint
        prompt = self_repair_prompt(
            issue=issue,
            fingerprint=fingerprint,
            evidence=str(inputs.get("failure_evidence") or ""),
        )
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

    if atom == "self_repair_validate":
        worktree = str(up.get("self_repair_prepare", {}).get("worktree") or "")
        assert worktree
        return _run_atom_main(self_repair_validate.main, ["--worktree", worktree])

    if atom == "self_repair_commit":
        worktree = str(up.get("self_repair_prepare", {}).get("worktree") or "")
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and fingerprint
        return _run_atom_main(
            commit_all.main,
            [*cfg, *live, "--worktree", worktree, "--message", f"self-repair: {fingerprint}"],
        )

    if atom == "self_repair_push_main":
        prepared = up.get("self_repair_prepare", {})
        validated = up.get("self_repair_validate", {})
        worktree = str(prepared.get("worktree") or "")
        base_sha = str(prepared.get("base_sha") or "")
        assert worktree and base_sha and validated.get("validated") is True
        return _run_atom_main(
            self_repair_push_main.main,
            [*cfg, *live, "--worktree", worktree, "--base-sha", base_sha, "--validated"],
        )

    if atom == "self_repair_activate":
        commit = str(up.get("self_repair_push_main", {}).get("commit") or "")
        assert commit
        return _run_atom_main(
            self_repair_activate.main,
            [*cfg, *live, "--commit", commit],
        )

    if atom == "self_repair_preflight":
        activated = up.get("self_repair_activate", {})
        commit = str(activated.get("commit") or "")
        project = str(activated.get("path") or "")
        config_path = str(inputs.get("config_path") or inputs.get("config") or "")
        assert commit and project and config_path
        return _run_atom_main(
            self_repair_preflight.main,
            ["--config", config_path, "--project", project, "--commit", commit],
        )

    if atom == "self_repair_close":
        commit = str(up.get("self_repair_preflight", {}).get("commit") or "")
        assert issue_number is not None and commit
        return _run_atom_main(
            self_repair_close.main,
            [*cfg, *live, "--issue", str(issue_number), "--commit", commit],
        )

    if atom == "get_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            get_issue.main,
            [*cfg, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "triage_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            triage_issue.main,
            [*cfg, *live, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "intake_issue":
        assert repo and issue_number is not None
        argv = [*cfg, *live, "--repo", repo, "--issue", str(issue_number)]
        triage = up.get("triage_issue") or {}
        triage_decision = triage.get("decision")
        if isinstance(triage_decision, dict) and triage_decision.get("decision") == "ready":
            argv.append("--candidate-ready")
        if isinstance(triage_decision, dict) and triage_decision.get("decision") == "split":
            argv.append("--candidate-split")
        if inputs.get("require_ready"):
            argv.append("--require-ready")
        return _run_atom_main(intake_issue.main, argv)

    if atom == "issue_split":
        assert repo and issue_number is not None
        argv = [*cfg, *live, "--repo", repo, "--issue", str(issue_number)]
        intake = up.get("intake_issue") or {}
        intake_decision = intake.get("decision")
        if isinstance(intake_decision, dict):
            argv.extend(["--intake-decision", json.dumps(intake_decision, separators=(",", ":"))])
            if intake_decision.get("reason"):
                argv.extend(["--reason", str(intake_decision.get("reason"))])
        elif intake_decision:
            argv.extend(["--intake-decision", str(intake_decision)])
        # Also honor triage split when intake skipped after already-decided tracker demotion.
        triage = up.get("triage_issue") or {}
        triage_decision = triage.get("decision")
        if (
            isinstance(triage_decision, dict)
            and triage_decision.get("decision") == "split"
            and not (isinstance(intake_decision, dict) and intake_decision.get("decision"))
        ):
            argv.extend(["--intake-decision", "split", "--reason", str(triage_decision.get("reason") or "too_large_split")])
        return _run_atom_main(issue_split.main, argv)

    if atom == "pr_checks":
        assert repo and pr_number is not None
        return _run_atom_main(
            pr_checks.main,
            [*cfg, "--repo", repo, "--pr", str(pr_number)],
        )

    if atom == "pr_review":
        assert repo and pr_number is not None
        # The graph always contains the review effector, but review policy is
        # optional.  Bypass the executor entirely when deterministic merge is
        # configured; downstream merge treats merge_ok=true as approval.
        from lokay.config import load_config

        review_cfg = load_config(str(inputs.get("config_path") or inputs.get("config") or "") or None)
        if not review_cfg.require_llm_review:
            return {
                "ok": True,
                "skipped": True,
                "reason": "llm_review_not_required",
                "merge_ok": True,
                "repo": repo,
                "pr": pr_number,
            }
        checks = up.get("pr_checks") or {}
        argv = [
            *cfg,
            *live,
            "--repo",
            repo,
            "--pr",
            str(pr_number),
        ]
        if branch:
            argv.extend(["--branch", branch])
        checks_text = str(checks.get("text") or inputs.get("checks_text") or "")
        if checks_text:
            argv.extend(["--checks-text", checks_text])
        return _run_atom_main(pr_review.main, argv)

    if atom == "pr_merge":
        assert repo and pr_number is not None
        checks = up.get("pr_checks") or {}
        # Skip cleanly when checks are not mergeable under policy.
        if checks and not (
            checks.get("merge_ok")
            or checks.get("green")
            or checks.get("status") == "passed"
        ):
            return {
                "ok": True,
                "skipped": True,
                "reason": "checks_not_mergeable",
                "status": checks.get("status"),
                "repo": repo,
                "pr": pr_number,
            }
        review = up.get("pr_review") or {}
        if review:
            if (
                not review.get("merge_ok")
                and review.get("skipped")
                and review.get("reason") in {
                    "executor_disabled",
                    "invalid_review_json",
                    "llm_review_requires_executor",
                }
            ):
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": str(review.get("reason") or "pr_review_skipped"),
                    "repo": repo,
                    "pr": pr_number,
                    "review": review.get("decision"),
                }
            if not review.get("merge_ok"):
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "llm_review_not_approved",
                    "repo": repo,
                    "pr": pr_number,
                    "review": review.get("decision"),
                }
        return _run_atom_main(
            pr_merge.main,
            [*cfg, *live, "--repo", repo, "--pr", str(pr_number)],
        )

    if atom == "close_issue":
        assert repo
        if inputs.get("keep_issue_open"):
            return {"ok": True, "skipped": True, "reason": "self_repair_validation_pending"}
        merged = up.get("pr_merge") or {}
        # Only close after merge ran (live merged=true) or dry-run planned merge.
        if merged.get("skipped"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "pr_merge_skipped",
                "repo": repo,
                "pr": pr_number,
            }
        if not (merged.get("merged") or merged.get("planned")):
            return {
                "ok": True,
                "skipped": True,
                "reason": "pr_not_merged",
                "repo": repo,
                "pr": pr_number,
            }
        if issue_number is None and branch:
            prefix = str(inputs.get("branch_prefix") or "ai/fix")
            issue_number = issue_number_from_branch(branch, branch_prefix=prefix)
        if issue_number is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "issue_number_unknown",
                "branch": branch,
                "pr": pr_number,
            }
        comment = str(
            inputs.get("comment")
            or f"Closed by Lokay after merging PR #{pr_number}."
        )
        return _run_atom_main(
            close_issue.main,
            [
                *cfg,
                *live,
                "--repo",
                repo,
                "--issue",
                str(issue_number),
                "--comment",
                comment,
            ],
        )

    if atom == "assign_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            assign_issue.main,
            [*cfg, *live, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "make_branch":
        issue_obj = up.get("get_issue", {}).get("issue") or {}
        title = str(issue_obj.get("title") or inputs.get("title") or "")
        prefix = str(inputs.get("branch_prefix") or "ai/fix")
        assert repo and issue_number is not None
        return _run_atom_main(
            make_branch.main,
            [
                "--prefix",
                prefix,
                "--repo",
                repo,
                "--issue",
                str(issue_number),
                "--title",
                title,
            ],
        )

    if atom == "worktree_add":
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or ""
        )
        assert repo and branch
        # issue_to_pr has make_branch upstream → always reset onto origin/main.
        # pr_repair reuses the existing PR branch tip (no make_branch).
        argv = [*cfg, *live, "--repo", repo, "--branch", branch]
        if "make_branch" in up or not repair_mode:
            # Prefer reset when this is not an explicit repair path.
            if "make_branch" in up:
                argv.append("--reset-base")
        return _run_atom_main(worktree_add.main, argv)

    if atom == "run_agent":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        )
        assert worktree
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
            )
        else:
            issue_raw = up.get("get_issue", {}).get("issue") or {}
            issue = Issue.from_dict(issue_raw) if issue_raw else None
            assert issue is not None
            prompt = issue_fix_prompt(issue, branch=branch)
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

    if atom == "commit_all":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        if repair_mode and pr_number is not None:
            msg = str(inputs.get("message") or f"repair: {repo} PR #{pr_number} checks")
        else:
            n = issue_raw.get("number", issue_number)
            title = str(issue_raw.get("title") or "")[:60]
            msg = str(inputs.get("message") or f"fix: {repo}#{n} {title}")
        assert worktree
        return _run_atom_main(
            commit_all.main,
            [*cfg, *live, "--worktree", worktree, "--message", msg],
        )

    if atom == "push":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        )
        assert worktree and branch
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


def main() -> int:
    def handler(manifest: dict[str, Any]) -> dict[str, Any]:
        config = sdk.config(manifest)
        atom = str(config.get("atom") or manifest.get("process_id") or "")
        if not atom:
            raise RuntimeError("config.atom is required")
        if atom == "commit_all" and not os.environ.get("LOKAY_HEALTH_LEASE_PATH"):
            raise RuntimeError(
                "health lease path missing at Fala mutation boundary"
            )
        inputs = dict(sdk.declared_inputs(manifest))
        # path-level inputs often appear as empty declared; merge impulse-style keys from input
        for key, value in sdk.input_values(manifest).items():
            if key not in sdk.INJECTED_INPUT_KEYS and key not in inputs:
                inputs[key] = value
        up = _conduction_values(manifest)
        result = _handle(atom, inputs, up)
        # fail-closed: atom ok=false or exit!=0
        ok_flag = bool(result.get("ok", False)) and result.get("_exit", 0) == 0
        if result.get("status") == "failed":
            ok_flag = False
        if not ok_flag and not result.get("skipped"):
            # still write structured failure values for journal; raise to fail process
            values = {"ok": False, "atom": atom, **{k: v for k, v in result.items() if k != "_exit"}}
            # Raising marks effector failed in Fala
            raise RuntimeError(json.dumps(values, ensure_ascii=False)[:2000])
        values = {"ok": True, "atom": atom, **{k: v for k, v in result.items() if k != "_exit"}}
        return sdk.output(values=values)

    return sdk.run_manifest_effector(handler)


if __name__ == "__main__":
    raise SystemExit(main())

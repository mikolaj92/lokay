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

from lokay.models import Issue
from lokay.prompts import issue_fix_prompt, pr_body, repair_pr_prompt


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
        run_agent,
        triage_issue,
        worktree_add,
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

    if atom == "factory_tick":
        # Domain health (work_remaining/stall) is a successful parent effector
        # result, not a corrupt Fala execution. Preserve the complete envelope
        # and let the parent path normalizer restore its public ok/error fields.
        return {"ok": True, "tick": _run_atom_main(factory_tick.main, [*cfg, *live])}

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
            return {
                "ok": False,
                "error": "refusing live push: upstream commit_all.committed is not true",
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

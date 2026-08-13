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
from lokay.prompts import (
    issue_fix_prompt,
    local_test_repair_prompt,
    pr_body,
    repair_pr_prompt,
    self_repair_prompt,
)


def _localize_paths(up: dict[str, dict[str, Any]]) -> list[str]:
    """Paths from localize conduction; empty means fail-closed before agent."""
    raw = up.get("localize", {}).get("paths") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        rel = str(item or "").strip()
        if rel:
            out.append(rel)
    return out


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


def _test_local_ok(env: dict[str, Any] | None) -> bool:
    """Green suite, or an honest skip (no Python suite), counts as success.

    A recorded-red first probe (`ok: true, passed: false`) is NOT success —
    that envelope exists only so Fala can conduct the one-shot repair nest.
    """
    if not isinstance(env, dict) or not env:
        return False
    if env.get("passed") is False:
        return False
    if env.get("skipped") or env.get("reason") == "no_python_test_suite":
        return True
    return env.get("ok") is True


def _require_test_local(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_merge/pr_create need successful local tests.

    The issue_to_pr lane adds one bounded recheck (test_local_recheck) after
    the single repair patch. When that conduction exists, it is the verdict
    (a recorded-red first probe is expected — that is why the nest ran).
    pr_repair/pr_triage have no recheck node, so the first probe still gates.
    Missing key, ok:false, or a red suite returns an error envelope. None means go.
    """
    if "test_local" not in up:
        return {
            "ok": False,
            "error": "refusing: test_local conduction missing",
            "reason": "test_local_missing",
        }
    recheck = up.get("test_local_recheck")
    if recheck is not None:
        if _test_local_ok(recheck):
            return None
        return {
            "ok": False,
            "error": str(
                recheck.get("error")
                or "refusing: test_local_recheck did not succeed"
            ),
            "reason": "test_local_recheck_failed",
        }
    tl = up["test_local"]
    if not _test_local_ok(tl):
        return {
            "ok": False,
            "error": str(tl.get("error") or "refusing: test_local did not succeed"),
            "reason": "test_local_failed",
        }
    return None


def _require_push(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: pr_create only after a successful push conduction.

    A red local suite or a refused/failed push must never reach
    `gh pr create`. None means go.
    """
    push = up.get("push")
    if push is None:
        return {
            "ok": False,
            "error": "refusing: push conduction missing",
            "reason": "push_missing",
        }
    if push.get("ok") is not True:
        return {
            "ok": False,
            "error": str(push.get("error") or "refusing: push did not succeed"),
            "reason": "push_failed",
        }
    return None


def _require_real_diff(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_create need a real (non-plan-only) diff.

    Plan/localize evidence (``.lokay/approach.md``, ``.lokay/localize.json``)
    is not progress. Missing key or ok:false returns an error envelope.
    None means go.
    """
    env = up.get("assert_real_diff")
    if env is None:
        return {
            "ok": False,
            "error": "refusing: assert_real_diff conduction missing",
            "reason": "real_diff_missing",
        }
    if env.get("ok") is not True:
        return {
            "ok": False,
            "error": str(env.get("error") or "refusing: diff is not real progress"),
            "reason": str(env.get("reason") or "plan_only"),
        }
    return None


def _handle(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from lokay.proc import (
        assign_issue,
        close_issue,
        commit_all,
        closeout_prs,
        compute_health,
        dispatch_implement,
        dispatch_triage,
        factory_begin,
        factory_tick,
        get_issue,
        host_ff,
        list_prs,
        make_branch,
        plan_issue,
        localize,
        plan_pass,
        pr_checks,
        pr_create,
        pr_label,
        pr_merge,
        pr_review,
        push_branch,
        record_pass,
        recovery_begin,
        recovery_incident,
        recovery_mill,
        recovery_observe,
        recovery_record,
        recovery_run_self_repair,
        resolve_conflicts,
        run_agent,
        select_implement,
        queue_conflict,
        stage_label,
        survey_inbox,
        survey_prs,
        survey_ready,
        survey_repos,
        test_local,
        triage_issue,
        intake_issue,
        issue_split,
        worktree_add,
        assert_real_diff,
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
        # Legacy alias (not in parent factory_pass). Invokes the same Fala
        # factory_pass mill as lokay-factory-pass — not an in-process spine.
        return {"ok": True, "tick": _run_atom_main(factory_tick.main, [*cfg, *live])}

    if atom == "host_ff":
        argv = [*cfg, *live]
        checkout = inputs.get("checkout") or os.environ.get("LOKAY_ROOT")
        if checkout:
            argv.extend(["--checkout", str(checkout)])
        return _run_atom_main(host_ff.main, argv)

    if atom == "factory_begin":
        return _run_atom_main(factory_begin.main, [*cfg, *live])

    if atom == "survey_repos":
        # Legacy bridge atom (not in parent factory_pass graph).
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            survey_repos.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "survey_prs":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            survey_prs.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "survey_inbox":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            survey_inbox.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "survey_ready":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            survey_ready.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "plan_pass":
        pass_dir = str(
            up.get("factory_begin", {}).get("pass_dir")
            or up.get("survey_ready", {}).get("pass_dir")
            or up.get("survey_repos", {}).get("pass_dir")
            or ""
        )
        assert pass_dir
        return _run_atom_main(plan_pass.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "dispatch_triage":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            dispatch_triage.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "resolve_conflicts":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            resolve_conflicts.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "closeout_prs":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            closeout_prs.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "select_implement":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            select_implement.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "queue_conflict":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            queue_conflict.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "dispatch_implement":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            dispatch_implement.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "compute_health":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            compute_health.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "record_pass":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        # Domain health (stall/work_remaining) is successful conduction; the
        # tick envelope inside may still set ok=false for the mill.
        return _run_atom_main(record_pass.main, [*cfg, *live, "--pass-dir", pass_dir])

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
        from lokay.config import load_config
        from lokay.merge_policy import decide_auto_merge

        merge_cfg = load_config(
            str(inputs.get("config_path") or inputs.get("config") or "") or None
        )
        checks = up.get("pr_checks") or {}
        review = up.get("pr_review") or {}
        # Trusted auto-merge gate (fail closed). Pending → waiting; red → repair;
        # secrets / needs_human / escalated needs-review never merge.
        gate = decide_auto_merge(
            merge_enabled=bool(merge_cfg.merge_enabled),
            require_checks=bool(merge_cfg.require_checks),
            require_llm_review=bool(merge_cfg.require_llm_review),
            checks=checks,
            review=review,
            pr_labels=inputs.get("pr_labels") or inputs.get("labels"),
        )
        if gate.action != "merge":
            return {
                "ok": True,
                "skipped": True,
                "reason": gate.reason,
                "status": checks.get("status"),
                "repo": repo,
                "pr": pr_number,
                "review": review.get("decision") if isinstance(review, dict) else None,
                "repairable": gate.repairable,
                "waiting": gate.waiting,
                "needs_review": gate.needs_review,
                "merge_policy": gate.to_dict(),
            }
        refused = _require_test_local(up)
        if refused is not None:
            return refused
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

    if atom == "stage_label":
        stage = str(inputs.get("stage") or "").strip().lower()
        if not stage:
            return {"ok": False, "error": "stage_label requires config/input stage"}
        if issue_number is None and branch:
            prefix = str(inputs.get("branch_prefix") or "ai/fix")
            issue_number = issue_number_from_branch(branch, branch_prefix=prefix)
        if issue_number is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "issue_number_unknown",
                "stage": stage,
                "branch": branch,
                "pr": pr_number,
            }
        # clear/merged only after a real (or planned) merge in pr_triage.
        if stage in {"clear", "merged"}:
            merged = up.get("pr_merge") or {}
            if merged.get("skipped") or not (
                merged.get("merged") or merged.get("planned")
            ):
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "pr_not_merged",
                    "stage": stage,
                    "repo": repo,
                    "pr": pr_number,
                }
        argv = [
            *cfg,
            *live,
            "--repo",
            repo,
            "--issue",
            str(issue_number),
            "--stage",
            stage,
        ]
        if inputs.get("receipt"):
            argv.append("--receipt")
        comment = str(inputs.get("comment") or "").strip()
        if comment:
            argv.extend(["--comment", comment])
        return _run_atom_main(stage_label.main, argv)

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
        # issue_to_pr has make_branch upstream → reset onto origin/main.
        # pr_repair / pr_triage reuse the existing PR branch tip (inputs.branch).
        argv = [*cfg, *live, "--repo", repo, "--branch", branch]
        if "make_branch" in up:
            argv.append("--reset-base")
        return _run_atom_main(worktree_add.main, argv)

    if atom == "plan_issue":
        worktree = str(up.get("worktree_add", {}).get("worktree") or inputs.get("worktree") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        assert worktree
        if not issue_raw and issue_number is not None and repo:
            issue_raw = {
                "repo": repo,
                "number": issue_number,
                "title": str(inputs.get("title") or ""),
                "body": str(inputs.get("body") or ""),
                "labels": [],
                "assignees": [],
                "url": str(inputs.get("url") or ""),
            }
        assert issue_raw
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(issue_raw, fh, ensure_ascii=False)
            issue_path = fh.name
        try:
            return _run_atom_main(
                plan_issue.main,
                [*cfg, *live, "--worktree", worktree, "--issue-json", issue_path],
            )
        finally:
            Path(issue_path).unlink(missing_ok=True)

    if atom == "localize":
        worktree = str(up.get("worktree_add", {}).get("worktree") or inputs.get("worktree") or "")
        assert worktree
        argv = [*cfg, *live, "--worktree", worktree]
        issue_path = ""
        checks_path = ""
        try:
            if repair_mode:
                checks_text = str(
                    up.get("pr_checks", {}).get("text")
                    or inputs.get("checks_text")
                    or ""
                )
                review_text = json.dumps(
                    inputs.get("review") or {}, ensure_ascii=False, sort_keys=True
                )
                seed = "\n\n".join(
                    part for part in (checks_text, review_text) if part and str(part).strip()
                )
                if not seed.strip():
                    seed = f"repair PR #{pr_number} in {repo}" if pr_number else f"repair in {repo}"
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".md", delete=False, encoding="utf-8"
                ) as fh:
                    fh.write(seed)
                    checks_path = fh.name
                argv.extend(["--seed-file", checks_path])
                if repo:
                    argv.extend(["--repo", repo])
            else:
                issue_raw = up.get("get_issue", {}).get("issue") or {}
                if not issue_raw and issue_number is not None and repo:
                    issue_raw = {
                        "repo": repo,
                        "number": issue_number,
                        "title": str(inputs.get("title") or ""),
                        "body": str(inputs.get("body") or ""),
                        "labels": [],
                        "assignees": [],
                        "url": str(inputs.get("url") or ""),
                    }
                assert issue_raw
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as fh:
                    json.dump(issue_raw, fh, ensure_ascii=False)
                    issue_path = fh.name
                argv.extend(["--issue-json", issue_path])
            return _run_atom_main(localize.main, argv)
        finally:
            if issue_path:
                Path(issue_path).unlink(missing_ok=True)
            if checks_path:
                Path(checks_path).unlink(missing_ok=True)

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
        # Effector config may carry stage/receipt for lokay-stage-label nodes.
        for key, value in config.items():
            if key == "atom":
                continue
            inputs.setdefault(key, value)
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

"""Fala bindings for physical commit, verification, and publication effects."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.organ.common import (
    _issue_no_longer_open,
    _issue_raw,
    _require_acceptance,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _worktree_path,
)
from lokay.prompts import pr_body


def handle_publication(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        commit_all,
        get_issue,
        push_branch,
        rebase_onto_base,
    )
    from lokay.proc._common import runner

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]
    repo_flags = ["--repo", repo] if repo else []
    from lokay.atom_runtime import run_atom_main
    from lokay.git_commit import branch_ahead_of_upstream as _branch_ahead

    _run_atom_main = ctx.get("run_atom_main") or run_atom_main
    branch_ahead_of_upstream = ctx.get("branch_ahead_of_upstream") or _branch_ahead
    if atom == "commit_all":
        worktree = _worktree_path(up, inputs)
        assert worktree
        gate = next(
            (
                up[name]
                for name in (
                    "assert_implementation_diff",
                    "assert_initial_repair_diff",
                    "assert_test_repair_diff",
                    "assert_repair_diff",
                    "assert_real_diff",
                )
                if name in up
            ),
            None,
        )
        if not isinstance(gate, dict) or gate.get("real") is not True:
            return {
                "ok": False,
                "error": str(
                    (gate or {}).get("error")
                    or "refusing commit: real-diff conduction missing or failed"
                ),
                "reason": str((gate or {}).get("reason") or "real_diff_missing"),
                "committed": False,
                "kind": (gate or {}).get("kind"),
            }
        issue_raw = _issue_raw(up, inputs)
        if repair_mode and pr_number is not None:
            msg = str(inputs.get("message") or f"repair: {repo} PR #{pr_number} checks")
        else:
            n = issue_raw.get("number", issue_number)
            title = str(issue_raw.get("title") or "")[:60]
            msg = str(inputs.get("message") or f"fix: {repo}#{n} {title}")
        assert worktree
        out = _run_atom_main(
            commit_all.main,
            [*cfg, *live, "--worktree", worktree, "--message", msg,
             *(["--record-repair-revision"] if repair_mode else [])],
        )
        if (repair_mode and inputs.get("live") and isinstance(out, dict)
                and out.get("ok") is True and out.get("committed") is True):
            import sqlite3

            from lokay.proc.repair_agent_revision import verified_commit_target
            try:
                verified_commit_target(commit=out, inputs=inputs, worktree=worktree,
                                       run_ref=dict(inputs.get("repair_run_ref") or {}))
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                return {**out, "ok": False, "reason": "repair_commit_revision_unverified", "error": str(exc)}
        if (
            isinstance(out, dict)
            and out.get("ok") is True
            and inputs.get("live")
            and out.get("committed") is not True
            and branch_ahead_of_upstream(runner(), Path(worktree), live=True) > 0
        ):
            if repair_mode:
                import sqlite3

                from lokay.proc.repair_agent_revision import observe, verified_target

                try:
                    target = verified_target(
                        inputs=inputs, run_ref=dict(inputs.get("repair_run_ref") or {}),
                        worktree=worktree,
                    )
                    if observe(runner(), Path(worktree)).get("head") != target:
                        raise ValueError("agent revision changed before commit gate")
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    return {**out, "ok": False, "reason": "repair_agent_revision_unverified", "error": str(exc)}
                out["commit"] = target
            out["committed"] = True
            out["committed_by"] = "agent"
        return out

    if atom == "rebase_onto_base":
        worktree = _worktree_path(up, inputs)
        assert worktree
        return _run_atom_main(
            rebase_onto_base.main, [*cfg, *live, *repo_flags, "--worktree", worktree]
        )

    if atom in {"test_local", "test_local_execution"}:
        worktree = _worktree_path(up, inputs)
        assert worktree
        argv = [*repo_flags, "--worktree", worktree]
        if inputs.get("changed_scope"):
            argv.append("--changed-scope")
        from lokay.proc.test_local_execution_subflow import run

        test_args: dict[str, Any] = {
            "worktree": worktree,
            "changed_scope": bool(inputs.get("changed_scope")),
            "repo": str(ctx.get("repo") or inputs.get("repo") or ""),
            "issue": ctx.get("issue_number") or inputs.get("issue"),
        }
        if "publish_pr_review" in up:
            from lokay.organ.lanes import run_merge_tests

            out = run_merge_tests(run, review=up["publish_pr_review"], **test_args)
        else:
            out = run(**test_args)
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
        worktree = _worktree_path(up, inputs)
        assert worktree
        from lokay.proc.assert_real_diff_subflow import run as run_real_diff

        issue_raw = _issue_raw(up, inputs)
        return run_real_diff(
            worktree=worktree,
            base="@{upstream}" if repair_mode else "origin/main",
            issue_body=str(issue_raw.get("body") or ""),
            repo=repo,
        )

    if atom == "push":
        worktree = _worktree_path(up, inputs)
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
        refused = _require_acceptance(up)
        if refused is not None:
            return refused
        from lokay.organ.common import _require_publish_gate

        refused = _require_publish_gate(up)
        if refused is not None:
            return refused
        committed = next(
            (
                (up.get(name) or {}).get("committed")
                for name in (
                    "commit_all",
                    "commit_implementation",
                    "commit_repair",
                    "commit_initial_repair",
                    "commit_test_repair",
                )
                if up.get(name)
            ),
            None,
        )
        if inputs.get("live") and committed is not True:
            unpublished = (
                branch_ahead_of_upstream(runner(), Path(worktree), live=True) > 0
            )
            if not unpublished:
                return {
                    "ok": False,
                    "error": "refusing live push: no new commit to publish",
                    "reason": "zero_diff",
                    "committed": committed,
                    "worktree": worktree,
                    "branch": branch,
                }
        if repair_mode and pr_number is not None and inputs.get("live"):
            from lokay.proc.pr_repair_push import prepare_live_push

            prepared = prepare_live_push(
                config_path=str(inputs.get("config_path") or "") or None,
                repo=repo, pr=int(pr_number), branch=branch, worktree=worktree,
                start_head_sha=str(inputs.get("head_sha") or inputs.get("repair_start_head_sha") or ""),
                repair_kind=str(inputs.get("repair_kind") or ""),
                reviewed_head_sha=str(inputs.get("reviewed_head_sha") or ""),
                task=inputs.get("task") or {},
                findings=inputs.get("findings") or [],
                task_identity_sha256=str(inputs.get("task_identity_sha256") or ""),
                review_result_sha256=str(inputs.get("review_result_sha256") or ""),
            )
            if prepared.get("route") != "ready":
                return {
                    "ok": False,
                    "error": "repair push intent could not be durably prepared",
                    "reason": str(prepared.get("reason") or "repair_push_intent_failed"),
                    "intent": prepared,
                    "worktree": worktree,
                    "branch": branch,
                }
            pushed = _run_atom_main(
                push_branch.main,
                [*cfg, *live, *repo_flags, "--worktree", worktree, "--branch", branch],
            )
            return {
                **dict(pushed or {}),
                "repair_push_intent_sha256": prepared["intent_sha256"],
            }
        return _run_atom_main(
            push_branch.main,
            [*cfg, *live, *repo_flags, "--worktree", worktree, "--branch", branch],
        )

    if atom == "pr_create":
        refused = _issue_no_longer_open(
            up,
            cfg=cfg,
            live=live,
            repo=repo,
            issue_number=issue_number,
            run=_run_atom_main,
            get_issue_main=get_issue.main,
        )
        if refused is not None:
            return refused
        refused = _require_test_local(up)
        if refused is not None:
            return refused
        refused = _require_real_diff(up)
        if refused is not None:
            return refused
        refused = _require_push(up)
        if refused is not None:
            return refused
        refused = _require_acceptance(up)
        if refused is not None:
            return refused
        from lokay.organ.common import _require_publish_gate

        refused = _require_publish_gate(up)
        if refused is not None:
            return refused
        branch = str(up.get("make_branch", {}).get("branch") or "")
        issue_raw = _issue_raw(up, inputs)
        issue = Issue.from_dict(issue_raw)
        agent = up.get("run_agent", {})
        summary = str(agent.get("stdout_tail") or agent.get("status") or "")
        acceptance = up.get("finalize_acceptance") or up.get("verify_acceptance") or {}
        session = up.get("coding_execution") or {}
        receipt = inputs.get("delivery_receipt") or {
            "repo": repo, "issue": issue.number, "work_id": f"{repo}#{issue.number}", "branch": branch,
            "graph_digest": str(session.get("graph_digest") or "pending"),
            "path_digest": str(session.get("path_digest") or "pending"),
            "run_refs": list(session.get("run_refs") or []),
            "acceptance_identity": acceptance.get("identity"),
            "acceptance_accepted": acceptance.get("accepted") is True,
            "builder_session": str(session.get("session") or "unavailable"),
            "reviewer_session": "pending", "acceptance_digest": str(acceptance.get("acceptance_digest") or acceptance.get("digest") or "pending"),
            "head_sha": str((up.get("push") or {}).get("head_sha") or inputs.get("head_sha") or "pending"),
        }
        body = pr_body(
            issue,
            agent_summary=summary,
            incident_fingerprint=str(inputs.get("incident_fingerprint") or ""),
            delivery_receipt=receipt,
        )
        title = f"fix: {repo}#{issue.number} {issue.title[:72]}"
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(body)
            body_path = fh.name
        try:
            from lokay.proc.pr_create_subflow import run

            return run(
                config_path=str(inputs.get("config_path") or "") or None,
                live=bool(inputs.get("live")),
                repo=repo,
                issue=issue_number,
                title=title,
                body=Path(body_path).read_text(encoding="utf-8"),
                head=branch,
                base="main",
            )
        finally:
            Path(body_path).unlink(missing_ok=True)


    if atom == "list_dirty_stamp_paths":
        worktree = _worktree_path(up, inputs)
        assert worktree
        from lokay.proc.list_dirty_stamp_paths import list_paths

        return list_paths(worktree, live=bool(inputs.get("live")))

    if atom == "commit_stamp_files":
        worktree = _worktree_path(up, inputs)
        assert worktree
        from lokay.proc.commit_stamp_files import commit

        issue_raw = _issue_raw(up, inputs)
        n = issue_raw.get("number", issue_number)
        msg = str(
            inputs.get("message")
            or f"chore: commit Done-means stamps for {repo}#{n}"
        )
        return commit(worktree, message=msg, live=bool(inputs.get("live")))

    if atom == "assert_stamps_committed":
        listed = up.get("list_dirty_stamp_paths") or {}
        # After commit_stamp_files, re-list is preferred; fall back to prior list.
        if "commit_stamp_files" in up:
            worktree = _worktree_path(up, inputs)
            assert worktree
            from lokay.proc.list_dirty_stamp_paths import list_paths

            listed = list_paths(worktree, live=bool(inputs.get("live")))
        from lokay.proc.assert_stamps_committed import assert_clean

        return assert_clean(listed)

    if atom == "local_verification_terminal":
        from lokay.proc.local_verification_terminal import terminal

        return terminal(up.get("finalize_local_tests") or {})

    if atom == "select_publish_gate":
        from lokay.proc.select_publish_gate import select

        return select(
            finalize_local_tests=up.get("finalize_local_tests") or {},
            finalize_acceptance=up.get("finalize_acceptance") or {},
            verify_acceptance=up.get("verify_acceptance_recheck")
            or up.get("verify_acceptance")
            or {},
            assert_stamps_committed=up.get("assert_stamps_committed") or {},
        )

    return None

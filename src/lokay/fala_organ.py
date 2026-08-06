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
from lokay.prompts import issue_fix_prompt, pr_body


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
        commit_all,
        get_issue,
        list_prs,
        make_branch,
        pr_create,
        pr_label,
        push_branch,
        run_agent,
        triage_issue,
        worktree_add,
    )

    cfg = _cfg_flags(inputs)
    live = _live_flags(inputs)
    repo = str(inputs.get("repo") or up.get("get_issue", {}).get("issue", {}).get("repo") or "")
    issue_number = inputs.get("issue") or inputs.get("issue_number")
    if issue_number is None and "get_issue" in up:
        issue_number = up["get_issue"].get("issue", {}).get("number")
    issue_number = int(issue_number) if issue_number is not None else None

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
        branch = str(up.get("make_branch", {}).get("branch") or inputs.get("branch") or "")
        assert repo and branch
        return _run_atom_main(
            worktree_add.main,
            [*cfg, *live, "--repo", repo, "--branch", branch],
        )

    if atom == "run_agent":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(up.get("make_branch", {}).get("branch") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        issue = Issue.from_dict(issue_raw) if issue_raw else None
        assert worktree and issue is not None
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
        n = issue_raw.get("number", issue_number)
        title = str(issue_raw.get("title") or "")[:60]
        msg = str(inputs.get("message") or f"fix: {repo}#{n} {title}")
        assert worktree
        return _run_atom_main(
            commit_all.main,
            [*live, "--worktree", worktree, "--message", msg],
        )

    if atom == "push":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(up.get("make_branch", {}).get("branch") or "")
        assert worktree and branch
        return _run_atom_main(
            push_branch.main,
            [*live, "--worktree", worktree, "--branch", branch],
        )

    if atom == "pr_create":
        branch = str(up.get("make_branch", {}).get("branch") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        issue = Issue.from_dict(issue_raw)
        agent = up.get("run_agent", {})
        summary = str(agent.get("stdout_tail") or agent.get("status") or "")
        body = pr_body(issue, agent_summary=summary)
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

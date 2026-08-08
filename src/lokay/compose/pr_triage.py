"""Composer: PR triage — checks → merge → close linked issue.

Order matches Fala path `pr_triage`. Default engine: Unix atomics
(LOKAY_USE_FALA=1 to force Fala host).
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.compose._atoms import run_atom, use_fala
from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.proc import close_issue as p_close
from lokay.proc import pr_checks as p_checks
from lokay.proc import pr_review as p_review
from lokay.proc import pr_merge as p_merge
from lokay.proc._common import add_config_live
from lokay.state import append_event
from lokay.stuck import issue_number_from_branch


def _atomic_pr_triage(
    *,
    config_path: str | None,
    repo: str,
    pr_number: int,
    branch: str,
    live: bool,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    steps: list[dict[str, Any]] = []

    chk = run_atom(
        p_checks.main,
        [*cfg_flag, "--repo", repo, "--pr", str(pr_number)],
    )
    steps.append({"step": "pr_checks", **chk})
    if not chk.get("ok"):
        return {"ok": False, "error": "pr_checks failed", "engine": "atoms", "steps": steps}

    status = str(chk.get("status") or "")
    can_merge = bool(chk.get("merge_ok")) or status == "passed" or (
        status == "none" and not cfg.require_checks
    )
    if not can_merge:
        return {
            "ok": True,
            "skipped": True,
            "reason": "checks_not_mergeable",
            "engine": "atoms",
            "status": status,
            "steps": steps,
        }

    # Optional LLM structured review before merge (fail closed).
    if cfg.require_llm_review and cfg.executor_enabled:
        rev = run_atom(
            p_review.main,
            [
                *cfg_flag,
                *live_flag,
                "--repo",
                repo,
                "--pr",
                str(pr_number),
                "--branch",
                branch,
                "--checks-text",
                str(chk.get("text") or ""),
            ],
        )
        steps.append({"step": "pr_review", **rev})
        if not rev.get("ok"):
            return {
                "ok": False,
                "error": rev.get("error") or "pr_review failed",
                "engine": "atoms",
                "steps": steps,
            }
        if rev.get("skipped") and rev.get("reason") in {
            "executor_disabled",
            "invalid_review_json",
        }:
            return {
                "ok": True,
                "skipped": True,
                "reason": str(rev.get("reason") or "pr_review_skipped"),
                "engine": "atoms",
                "review": rev.get("decision"),
                "steps": steps,
            }
        if not rev.get("merge_ok"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "llm_review_not_approved",
                "engine": "atoms",
                "review": rev.get("decision"),
                "steps": steps,
            }
    elif cfg.require_llm_review and not cfg.executor_enabled:
        return {
            "ok": True,
            "skipped": True,
            "reason": "llm_review_requires_executor",
            "engine": "atoms",
            "steps": steps,
        }

    if not cfg.merge_enabled:
        return {
            "ok": True,
            "skipped": True,
            "reason": "merge_disabled",
            "engine": "atoms",
            "steps": steps,
        }

    merged = run_atom(
        p_merge.main,
        [*cfg_flag, *live_flag, "--repo", repo, "--pr", str(pr_number)],
    )
    steps.append({"step": "pr_merge", **merged})
    if not merged.get("ok"):
        err_txt = str(merged.get("error") or "pr_merge failed")
        # Conflicts are not a machine stall of the whole mill — isolate this PR.
        if "merge conflict" in err_txt.lower() or "merge conflicts" in err_txt.lower():
            return {
                "ok": True,
                "skipped": True,
                "reason": "merge_conflicts",
                "engine": "atoms",
                "error": err_txt,
                "steps": steps,
            }
        return {"ok": False, "error": err_txt, "engine": "atoms", "steps": steps}
    if live and not merged.get("merged"):
        return {"ok": False, "error": "pr_merge did not merge", "engine": "atoms", "steps": steps}

    issue_n = issue_number_from_branch(branch, branch_prefix=cfg.branch_prefix)
    if issue_n is None:
        return {
            "ok": True,
            "engine": "atoms",
            "merged": bool(merged.get("merged") or not live),
            "closed_issue": None,
            "steps": steps,
            "note": "no issue number in branch name",
        }

    closed = run_atom(
        p_close.main,
        [
            *cfg_flag,
            *live_flag,
            "--repo",
            repo,
            "--issue",
            str(issue_n),
            "--comment",
            f"Closed by Lokay after merging PR #{pr_number}.",
        ],
    )
    steps.append({"step": "close_issue", "issue": issue_n, **closed})
    return {
        "ok": bool(closed.get("ok")),
        "engine": "atoms",
        "merged": bool(merged.get("merged") or not live),
        "closed_issue": issue_n if closed.get("ok") else None,
        "steps": steps,
        "error": closed.get("error"),
    }


def compose_pr_triage(
    *,
    config_path: str | None,
    repo: str,
    pr_number: int,
    branch: str,
    live: bool,
) -> dict:
    if live:
        cfg = load_config(config_path)
        if cfg.mode != "live":
            return {
                "ok": False,
                "error": "refusing live compose while config mode is not live",
            }
    if not branch:
        return {"ok": False, "error": "branch required for pr_triage"}

    if use_fala():
        from lokay.graph_run import run_path

        result = run_path(
            path_id="pr_triage",
            repo=repo,
            pr=pr_number,
            branch=branch,
            config_path=config_path,
            live=live,
        )
        result["kind"] = "pr_triage"
        result["engine"] = "fala"
        result["planned"] = not live
    else:
        result = _atomic_pr_triage(
            config_path=config_path,
            repo=repo,
            pr_number=pr_number,
            branch=branch,
            live=live,
        )
        result["kind"] = "pr_triage"
        result["planned"] = not live

    try:
        cfg = load_config(config_path)
        append_event(cfg.state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-triage")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--branch", required=True, help="head ref of the PR")
    args = p.parse_args(argv)
    payload = compose_pr_triage(
        config_path=args.config,
        repo=args.repo,
        pr_number=int(args.pr),
        branch=str(args.branch),
        live=bool(args.live),
    )
    return emit_exit(payload if "ok" in payload else {**payload, "ok": bool(payload.get("ok"))})


if __name__ == "__main__":
    raise SystemExit(main())

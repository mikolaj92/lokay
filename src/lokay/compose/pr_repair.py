"""Composer: repair open AI PR after failed checks.

Order matches Fala path `pr_repair`. Default engine: Unix atomics
(LOKAY_USE_FALA=1 to force Fala host).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.compose._atoms import run_atom, unlink_quiet, use_fala, write_temp
from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.proc import commit_all as p_commit
from lokay.proc import pr_checks as p_checks
from lokay.proc import push_branch as p_push
from lokay.proc import run_agent as p_agent
from lokay.proc import worktree_add as p_worktree
from lokay.proc._common import add_config_live
from lokay.prompts import repair_pr_prompt
from lokay.state import append_event


def _atomic_pr_repair(
    *,
    config_path: str | None,
    repo: str,
    pr_number: int,
    branch: str,
    live: bool,
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    wt = run_atom(
        p_worktree.main,
        [*cfg_flag, *live_flag, "--repo", repo, "--branch", branch],
    )
    steps.append({"step": "worktree_add", **wt})
    if not wt.get("ok"):
        return {"ok": False, "error": wt.get("error") or "worktree_add failed", "engine": "atoms", "steps": steps}
    worktree = str(wt.get("worktree") or "")

    prompt = repair_pr_prompt(
        repo=repo,
        pr_number=pr_number,
        branch=branch,
        checks_text=str(chk.get("text") or ""),
        review_text=json.dumps(review or {}, ensure_ascii=False, sort_keys=True),
    )
    prompt_path = write_temp(prompt)
    try:
        agent = run_atom(
            p_agent.main,
            [*cfg_flag, *live_flag, "--worktree", worktree, "--prompt-file", prompt_path],
        )
    finally:
        unlink_quiet(prompt_path)
    steps.append({"step": "run_agent", **agent})
    if not agent.get("ok") or agent.get("status") == "failed":
        return {"ok": False, "error": "run_agent failed", "engine": "atoms", "steps": steps}

    committed = run_atom(
        p_commit.main,
        [
            *live_flag,
            "--worktree",
            worktree,
            "--message",
            f"repair: {repo} PR #{pr_number} checks",
        ],
    )
    steps.append({"step": "commit_all", **committed})
    if not committed.get("ok"):
        return {"ok": False, "error": "commit_all failed", "engine": "atoms", "steps": steps}
    if live and not committed.get("committed"):
        return {
            "ok": False,
            "error": "repair produced no commit",
            "engine": "atoms",
            "steps": steps,
        }

    pushed = run_atom(
        p_push.main,
        [*live_flag, "--worktree", worktree, "--branch", branch],
    )
    steps.append({"step": "push", **pushed})
    if not pushed.get("ok"):
        return {"ok": False, "error": pushed.get("error") or "push failed", "engine": "atoms", "steps": steps}

    return {"ok": True, "engine": "atoms", "repo": repo, "pr": pr_number, "branch": branch, "steps": steps}


def compose_pr_repair(
    *,
    config_path: str | None,
    repo: str,
    pr_number: int,
    branch: str,
    live: bool,
    review: dict[str, Any] | None = None,
) -> dict:
    if live:
        cfg = load_config(config_path)
        if cfg.mode != "live":
            return {
                "ok": False,
                "error": "refusing live compose while config mode is not live",
            }
        if not branch:
            return {"ok": False, "error": "branch required for pr_repair"}

    if use_fala():
        from lokay.graph_run import run_path

        result = run_path(
            path_id="pr_repair",
            repo=repo,
            pr=pr_number,
            branch=branch,
            config_path=config_path,
            live=live,
            extra_inputs={"review": review or {}},
        )
        result["kind"] = "pr_repair"
        result["engine"] = "fala"
        result["planned"] = not live
    else:
        result = _atomic_pr_repair(
            config_path=config_path,
            repo=repo,
            pr_number=pr_number,
            branch=branch,
            live=live,
            review=review,
        )
        result["kind"] = "pr_repair"
        result["planned"] = not live

    try:
        cfg = load_config(config_path)
        append_event(cfg.state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-repair")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--branch", required=True, help="head ref of the PR")
    p.add_argument("--review-json", default="", help="structured request_changes evidence")
    args = p.parse_args(argv)
    try:
        review = json.loads(args.review_json) if args.review_json else None
    except json.JSONDecodeError as exc:
        return emit_exit({"ok": False, "error": f"invalid --review-json: {exc}"})
    payload = compose_pr_repair(
        config_path=args.config,
        repo=args.repo,
        pr_number=int(args.pr),
        branch=str(args.branch),
        live=bool(args.live),
        review=review,
    )
    return emit_exit(payload if "ok" in payload else {**payload, "ok": bool(payload.get("ok"))})


if __name__ == "__main__":
    raise SystemExit(main())

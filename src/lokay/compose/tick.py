"""Composer: intake + triage peek via atomics only."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from typing import Any, Callable

from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.envelope import emit_exit, err, ok
from lokay.proc import list_issues as p_list_issues
from lokay.proc import list_prs as p_list_prs
from lokay.proc import pr_checks as p_checks
from lokay.proc import select_issue as p_select
from lokay.proc._common import add_config_live, load_cfg


def _run(main_fn: Callable[..., int], argv: list[str]) -> dict[str, Any]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main_fn(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty process output", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def compose_tick(*, config_path: str | None, live: bool) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    if live and cfg.mode != "live":
        return err("refusing --live while config mode is not live")

    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    planned: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    if not live:
        planned.append(
            {
                "kind": "tick",
                "status": "planned",
                "repos": [r.name for r in cfg.repos],
                "agent": cfg.agent,
                "pipeline": [
                    "lokay-list-issues (read)",
                    "lokay-select-issue",
                    "lokay-issue-to-pr",
                    "lokay-list-prs + lokay-pr-checks",
                ],
            }
        )
        return ok(mode=cfg.mode, live=False, executed=False, planned=planned, actions=actions)

    selected = None
    for repo in cfg.repos:
        listed = _run(p_list_issues.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_issues", "repo": repo.name, **listed})
        if not listed.get("ok") or not listed.get("issues"):
            continue
        buf_in = json.dumps({"issues": listed["issues"]})
        buf_out = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stdin(io.StringIO(buf_in)):
            code = p_select.main([])
        sel = json.loads(buf_out.getvalue().strip().splitlines()[-1])
        sel["_exit"] = code
        actions.append({"step": "select_issue", **sel})
        if sel.get("selected"):
            selected = sel["selected"]
            break

    if selected:
        result = compose_issue_to_pr(
            config_path=config_path,
            repo=selected["repo"],
            issue_number=int(selected["number"]),
            live=True,
        )
        actions.append({"step": "issue_to_pr", **result})
    else:
        planned.append({"kind": "intake", "status": "idle"})

    for repo in cfg.repos:
        prs = _run(p_list_prs.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_prs", "repo": repo.name, **prs})
        for pr in prs.get("prs") or []:
            chk = _run(
                p_checks.main,
                [*cfg_flag, "--repo", repo.name, "--pr", str(pr["number"])],
            )
            actions.append({"step": "pr_checks", "pr": pr["number"], **chk})

    return ok(mode=cfg.mode, live=True, executed=True, planned=planned, actions=actions)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-tick")
    add_config_live(p)
    args = p.parse_args(argv)
    return emit_exit(compose_tick(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())

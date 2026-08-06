"""Composer: run the Fala pr_repair graph for one open AI PR."""

from __future__ import annotations

import argparse

from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live
from lokay.state import append_event


def compose_pr_repair(
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
            return {"ok": False, "error": "branch required for pr_repair"}

    result = run_path(
        path_id="pr_repair",
        repo=repo,
        pr=pr_number,
        branch=branch,
        config_path=config_path,
        live=live,
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
    args = p.parse_args(argv)
    payload = compose_pr_repair(
        config_path=args.config,
        repo=args.repo,
        pr_number=int(args.pr),
        branch=str(args.branch),
        live=bool(args.live),
    )
    return emit_exit(payload if "ok" in payload else {**payload, "ok": bool(payload.get("ok"))})


if __name__ == "__main__":
    raise SystemExit(main())

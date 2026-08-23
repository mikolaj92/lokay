"""CLI facade for authored one-PR closeout."""

import argparse
from pathlib import Path
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def run_closeout_pr(
    *,
    repo: str,
    pr: dict,
    config_path: str | None,
    live: bool,
    merge_enabled: bool,
    require_checks: bool,
    repair_budget: int,
    executor_enabled: bool,
    branch_prefix: str,
    stuck: dict,
    stuck_path: Path,
    catalog: list[str] | None = None,
) -> dict:
    from lokay.proc.closeout_pr_subflow import run

    selected = {
        "ok": True,
        "route": "closeout",
        "repo": repo,
        "pr": pr,
        "repair_budget": repair_budget,
        "policy": {
            "merge_enabled": merge_enabled,
            "require_checks": require_checks,
            "executor_enabled": executor_enabled,
            "branch_prefix": branch_prefix,
            "stuck_path": str(stuck_path),
        },
    }
    return run(selected=selected, config_path=config_path, live=live)


def main(argv=None):
    p = argparse.ArgumentParser(prog="lokay-closeout-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--head-ref", default="")
    p.add_argument("--merge-enabled", action="store_true")
    a = p.parse_args(argv)
    return emit_exit(
        run_closeout_pr(
            repo=a.repo,
            pr={"number": a.pr, "head_ref": a.head_ref, "labels": []},
            config_path=a.config,
            live=bool(a.live),
            merge_enabled=bool(a.merge_enabled),
            require_checks=False,
            repair_budget=0,
            executor_enabled=False,
            branch_prefix="ai/fix/",
            stuck={},
            stuck_path=Path(""),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

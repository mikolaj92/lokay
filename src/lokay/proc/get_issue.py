"""Atomic: load one issue by number (read-only)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_read, load_cfg, read_live, runner
from lokay.tasks import TaskId
from lokay.github_tasks import catalog_row, issues_source, task_to_issue




def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-get-issue")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = read_live(args)
    try:
        row = catalog_row(cfg, args.repo)
        source = issues_source(row, runner=runner(), config=cfg, live=live)
        task = source.get(TaskId(source.plugin, source.target, args.issue))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    if task is None:
        return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))
    return emit_exit(ok(offline=not live, issue=task_to_issue(task).to_dict()))


if __name__ == "__main__":
    raise SystemExit(main())

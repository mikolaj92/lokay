"""Read-only compatibility facade for the authored status snapshot."""

import argparse
from typing import Any

from lokay.compose.human_mailbox import compose_human_mailbox
from lokay.envelope import emit_exit
from lokay.proc._common import add_config


def compose_status(
    *,
    config_path: str | None,
    survey: bool = True,
    preflight_check: bool = False,
    human: bool = False,
) -> dict[str, Any]:
    if human:
        return compose_human_mailbox(config_path=config_path, live=True)
    if preflight_check or survey:
        from lokay.proc.status_snapshot_subflow import run
        return run(config_path=config_path, preflight=preflight_check, full=survey)

    from lokay.proc.classify_status_readiness import classify as classify_readiness
    from lokay.proc.describe_status_graphs import describe as describe_graphs
    from lokay.proc.read_status_clone_facts import read as read_clones
    from lokay.proc.read_status_config import read as read_config
    from lokay.proc.read_status_lease import read as read_lease
    from lokay.proc.read_status_pass_receipt import read as read_receipt
    from lokay.proc.read_status_repo_locks import read as read_repo_locks
    from lokay.proc.read_status_work_units import read as read_work_units
    from lokay.proc.reduce_status_snapshot import reduce as reduce_snapshot

    from lokay.proc.status_snapshot_terminal import terminal
    cfg = read_config(config_path=config_path, preflight=False, full=False)
    readiness = classify_readiness(cfg)
    clones = read_clones(cfg)
    lease = read_lease(cfg)
    receipt = read_receipt(cfg)
    work_fact = read_work_units(cfg)
    locks = read_repo_locks(cfg)
    graphs = describe_graphs()
    reduced = reduce_snapshot(cfg, readiness, clones, lease, receipt, work_fact, locks, graphs, {})
    return terminal(reduced).get("result") or reduced.get("snapshot") or {}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-status")
    add_config(p)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--local", "--skip-survey", action="store_true", dest="local")
    mode.add_argument("--full", action="store_true")
    mode.add_argument("--human", action="store_true")
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args(argv)
    return emit_exit(
        compose_status(
            config_path=args.config,
            survey=not args.local,
            preflight_check=bool(args.preflight and args.local),
            human=args.human,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

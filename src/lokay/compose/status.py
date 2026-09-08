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
    from lokay.proc.status_snapshot_subflow import run

    return run(config_path=config_path, preflight=preflight_check, full=survey)


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

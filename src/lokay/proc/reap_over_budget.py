"""CLI facade for the authored detached-worker budget Fala."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live
from lokay.proc.pi_budget import DEFAULT_BUDGET_S


def run_reap_over_budget(
    *,
    budget_s: int = DEFAULT_BUDGET_S,
    pass_dir: str | None = None,
    config_path: str | None = None,
    live: bool = False,
) -> dict:
    from lokay.proc.reap_over_budget_subflow import run

    return run(budget_s=budget_s, pass_dir=pass_dir, config_path=config_path, live=live)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-reap-over-budget")
    add_config_live(parser)
    parser.add_argument("--pass-dir", default="")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET_S)
    args = parser.parse_args(argv)
    if args.budget < 0:
        return emit_exit(err("budget must be >= 0", budget_s=args.budget))
    payload = run_reap_over_budget(
        budget_s=int(args.budget),
        pass_dir=str(args.pass_dir or "") or None,
        config_path=args.config,
        live=bool(args.live),
    )
    payload["pass_dir"] = str(args.pass_dir or "")
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())

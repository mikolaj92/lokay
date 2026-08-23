"""CLI facade for the authored pass-planning Fala."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def run_plan_pass(*, pass_dir: str) -> dict:
    from lokay.proc.plan_pass_subflow import run

    return run(pass_dir=pass_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-plan-pass")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(run_plan_pass(pass_dir=str(args.pass_dir)))


if __name__ == "__main__":
    raise SystemExit(main())

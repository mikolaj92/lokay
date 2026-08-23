"""CLI facade for the authored implementation-selection Fala."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def run_select_implement(*, pass_dir: str) -> dict:
    from lokay.proc.select_implement_subflow import run

    return run(pass_dir=pass_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-select-implement")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(run_select_implement(pass_dir=str(args.pass_dir)))


if __name__ == "__main__":
    raise SystemExit(main())

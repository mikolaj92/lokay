"""CLI facade for the authored serial implementation dispatch Fala."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-dispatch-implement")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    from lokay.proc.dispatch_implementation_subflow import run

    return emit_exit(
        run(pass_dir=str(args.pass_dir), config_path=args.config, live=bool(args.live))
    )


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI facade for the authored conflict-resolution Fala."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def run_resolve_conflicts(
    *, pass_dir: str, config_path: str | None, live: bool
) -> dict:
    from lokay.proc.resolve_conflicts_subflow import run

    return run(pass_dir=pass_dir, config_path=config_path, live=live)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-resolve-conflicts")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_resolve_conflicts(
            pass_dir=str(args.pass_dir), config_path=args.config, live=bool(args.live)
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

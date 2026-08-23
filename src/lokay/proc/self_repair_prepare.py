"""CLI facade for authored self-repair worktree preparation."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live

REPO = "mikolaj92/lokay"


def run_prepare(*, fingerprint: str, config_path: str | None, live: bool) -> dict:
    from lokay.proc.self_repair_prepare_subflow import run

    return run(fingerprint=fingerprint, config_path=config_path, live=live)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-self-repair-prepare")
    add_config_live(parser)
    parser.add_argument("--fingerprint", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_prepare(
            fingerprint=args.fingerprint, config_path=args.config, live=bool(args.live)
        )
    except Exception as exc:
        return emit_exit(err(str(exc)))
    return emit_exit(result)


if __name__ == "__main__":
    raise SystemExit(main())

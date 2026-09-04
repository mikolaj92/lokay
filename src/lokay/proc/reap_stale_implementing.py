"""CLI facade for the authored stale implementation-stage recovery Fala."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live
from lokay.proc.stale_implementing_stamp import (
    STALE_TTL_SECONDS,
    IDLE_STALE_TTL_SECONDS,
    STALE_STAMP_NAME,
    stale_stamp_path,
    lokay_stale_stamp_path,
    stale_recently_empty,
)


def run_reap_stale_implementing(
    *, pass_dir: str | None, config_path: str | None, live: bool
) -> dict:
    from lokay.proc.reap_stale_implementing_subflow import run

    return run(pass_dir=pass_dir, config_path=config_path, live=live)


def reap_idle_leftover_cache(*, config_path: str | None, live: bool = True) -> None:
    if not live:
        return
    try:
        run_reap_stale_implementing(pass_dir=None, config_path=config_path, live=True)
    except OSError:
        return


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-reap-stale-implementing")
    add_config_live(parser)
    parser.add_argument("--pass-dir", default="")
    args = parser.parse_args(argv)
    try:
        payload = run_reap_stale_implementing(
            pass_dir=str(args.pass_dir or "") or None,
            config_path=args.config,
            live=bool(args.live),
        )
    except Exception as exc:
        return emit_exit(err(str(exc)))
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())

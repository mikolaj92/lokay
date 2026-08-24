"""Thin CLI facade for authored exact self-repair activation."""

import argparse

from lokay.envelope import emit_exit, err


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-activate")
    p.add_argument("--config")
    p.add_argument("--live", action="store_true")
    p.add_argument("--commit", required=True)
    args = p.parse_args(argv)
    try:
        from lokay.proc.self_repair_activate_subflow import run

        out = run(config_path=args.config, live=bool(args.live), commit=args.commit)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
